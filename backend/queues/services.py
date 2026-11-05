"""Queue business rules and reporting, independent of HTTP views."""
import hashlib
import math
import re
import uuid

from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce

from .models import Manager, Queue, RateLimit, Token, timestamp_ms

MINUTE = 60_000
DAY = 86_400_000
COLORS = ["#0d6efd", "#198754", "#fd7e14", "#0dcaf0", "#6f42c1"]


class APIError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def text_field(value, label, maximum, required=True):
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise APIError(400, f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise APIError(400, f"{label} is required.")
    if len(value) > maximum:
        raise APIError(400, f"{label} must be {maximum} characters or fewer.")
    return value


def throttle(ip, category):
    now = timestamp_ms()
    key = hashlib.sha256(f"{ip}:{category}".encode()).hexdigest()
    with transaction.atomic():
        RateLimit.objects.filter(resets_at__lte=now).delete()
        record, _ = RateLimit.objects.select_for_update().get_or_create(key=key, defaults={"resets_at": now + 15 * MINUTE})
        record.count += 1
        record.save(update_fields=["count"])
        exceeded = record.count > (10 if category == "demo" else 40)
    if exceeded:
        raise APIError(429, "Too many attempts. Please try again in 15 minutes.")


def user_data(user):
    return {"id": str(user.id), "name": user.name, "email": user.email, "is_demo": user.is_demo}


def queue_data(queue):
    data = {key: getattr(queue, key) for key in ["name", "prefix", "color", "paused", "next_number", "revision", "created_at"]}
    data.update(id=str(queue.id), manager_id=str(queue.manager_id))
    for key in ["waiting", "serving", "completed"]:
        if hasattr(queue, key):
            data[key] = getattr(queue, key)
    return data


def token_data(token):
    data = {key: getattr(token, key) for key in ["number", "name", "note", "status", "position", "created_at", "started_at", "ended_at"]}
    data.update(id=str(token.id), queue_id=str(token.queue_id))
    return data


def owned_queue(manager, queue_id, lock=False):
    queryset = Queue.objects.select_for_update() if lock else Queue.objects
    queue = queryset.filter(pk=queue_id, manager=manager).first()
    if queue is None:
        raise APIError(404, "Queue not found.")
    return queue


def list_queues(manager):
    return Queue.objects.filter(manager=manager).annotate(
        waiting=Count("tokens", filter=Q(tokens__status="waiting")),
        serving=Count("tokens", filter=Q(tokens__status="serving")),
        completed=Count("tokens", filter=Q(tokens__status="completed")),
    ).order_by("created_at", "id")


def check_revision(queue, value):
    if type(value) is not int:
        raise APIError(400, "The queue revision is required. Refresh and try again.")
    if value != queue.revision:
        raise APIError(409, "This queue changed in another window. The latest queue has been loaded. Please try again.")


def bump_revision(queue, **changes):
    queue.revision += 1
    for key, value in changes.items():
        setattr(queue, key, value)
    queue.save(update_fields=["revision", *changes])


@transaction.atomic
def create_queue(manager, body):
    name = text_field(body.get("name"), "Queue name", 60)
    # Serialize the workspace's queue-count limit across concurrent requests.
    Manager.objects.select_for_update().get(pk=manager.pk)
    count = Queue.objects.filter(manager=manager).count()
    if count >= 50:
        raise APIError(400, "Your workspace can have up to 50 queues.")
    prefix = re.sub(r"[^a-z0-9]", "", "".join(word[0] for word in name.split()), flags=re.I)[:3].upper() or "Q"
    return Queue.objects.create(manager=manager, name=name, prefix=prefix, color=COLORS[count % len(COLORS)])


def queue_details(manager, queue_id):
    queue = owned_queue(manager, queue_id)
    tokens = list(queue.tokens.filter(status__in=["waiting", "serving"]))
    return {
        "queue": queue_data(queue),
        "waiting": [token_data(token) for token in tokens if token.status == "waiting"],
        "serving": next((token_data(token) for token in tokens if token.status == "serving"), None),
    }


@transaction.atomic
def add_token(manager, queue_id, body):
    name = text_field(body.get("name"), "Person name", 80)
    note = text_field(body.get("note"), "Note", 240, required=False)
    queue = owned_queue(manager, queue_id, lock=True)
    if queue.paused:
        raise APIError(409, "This queue is paused. Resume it before adding a person.")
    waiting = queue.tokens.filter(status="waiting").aggregate(count=Count("id"), position=Max("position"))
    if waiting["count"] >= 500:
        raise APIError(400, "This queue has reached its limit of 500 waiting people.")
    token = Token.objects.create(queue=queue, number=queue.next_number, name=name, note=note, position=(waiting["position"] or 0) + 1)
    bump_revision(queue, next_number=queue.next_number + 1)
    return token


@transaction.atomic
def move_token(manager, queue_id, token_id, body):
    direction = body.get("direction")
    if direction not in ["up", "down"]:
        raise APIError(400, "Direction must be up or down.")
    queue = owned_queue(manager, queue_id, lock=True)
    check_revision(queue, body.get("revision"))
    tokens = list(queue.tokens.filter(status="waiting"))
    index = next((i for i, token in enumerate(tokens) if token.id == token_id), None)
    if index is None:
        raise APIError(404, "Waiting token not found.")
    adjacent = index + (-1 if direction == "up" else 1)
    if adjacent < 0 or adjacent >= len(tokens):
        raise APIError(409, "This token is already at the end of the queue.")
    tokens[index].position, tokens[adjacent].position = tokens[adjacent].position, tokens[index].position
    Token.objects.bulk_update([tokens[index], tokens[adjacent]], ["position"])
    bump_revision(queue)


@transaction.atomic
def serve_next(manager, queue_id, body):
    queue = owned_queue(manager, queue_id, lock=True)
    check_revision(queue, body.get("revision"))
    if queue.paused:
        raise APIError(409, "Resume this queue before calling the next person.")
    if queue.tokens.filter(status="serving").exists():
        raise APIError(409, "Finish the current service before calling the next person.")
    token = queue.tokens.filter(status="waiting").first()
    if token is None:
        raise APIError(409, "There are no people waiting in this queue.")
    token.status, token.started_at = "serving", timestamp_ms()
    token.save(update_fields=["status", "started_at"])
    bump_revision(queue)
    return token


@transaction.atomic
def finish_token(manager, queue_id, token_id, action):
    queue = owned_queue(manager, queue_id, lock=True)
    token = queue.tokens.filter(pk=token_id).first()
    if token is None:
        raise APIError(404, "Token not found.")
    expected = "serving" if action == "complete" else "waiting"
    if token.status != expected:
        raise APIError(409, "Only a token currently in service can be completed." if action == "complete" else "Only a waiting token can be cancelled.")
    token.status = "completed" if action == "complete" else "cancelled"
    token.ended_at = timestamp_ms()
    token.save(update_fields=["status", "ended_at"])
    bump_revision(queue)


@transaction.atomic
def patch_queue(manager, queue_id, body):
    queue = owned_queue(manager, queue_id, lock=True)
    check_revision(queue, body.get("revision"))
    if type(body.get("paused")) is not bool:
        raise APIError(400, "Paused must be true or false.")
    bump_revision(queue, paused=body["paused"])


def integer_parameter(value, default, label):
    if value is None:
        return default
    try:
        if not re.fullmatch(r"-?\d+", str(value)):
            raise ValueError
        return int(value)
    except (ValueError, TypeError):
        raise APIError(400, f"Invalid {label}.")


def average_minutes(values):
    return math.floor(sum(values) / len(values) / MINUTE * 10 + 0.5) / 10 if values else None


def analytics(manager, params):
    days = integer_parameter(params.get("days"), 7, "period")
    offset = integer_parameter(params.get("offset"), 0, "timezone offset")
    if days not in [1, 7, 30]:
        raise APIError(400, "Choose a 1, 7, or 30 day period.")
    if abs(offset) > 840:
        raise APIError(400, "Invalid timezone offset.")
    queue_id = params.get("queueId")
    queues = list(list_queues(manager))
    queryset = Token.objects.filter(queue__manager=manager)
    if queue_id:
        try:
            queue_id = uuid.UUID(queue_id)
        except (ValueError, TypeError):
            raise APIError(404, "Queue not found.")
        owned_queue(manager, queue_id)
        queryset = queryset.filter(queue_id=queue_id)
        queues = [queue for queue in queues if queue.id == queue_id]
    tokens = list(queryset)
    now = timestamp_ms()
    today = (now - offset * MINUTE) // DAY * DAY + offset * MINUTE
    since = today - (days - 1) * DAY
    started = [token for token in tokens if token.started_at is not None and since <= token.started_at <= now]
    completed = [token for token in tokens if token.status == "completed" and since <= token.ended_at <= now]
    points = []
    interval = 60 * MINUTE if days == 1 else DAY
    for i in range(24 if days == 1 else days):
        begin = since + i * interval
        end = begin + interval
        boundary = min(end, now)
        waits = [token.started_at - token.created_at for token in started if begin <= token.started_at < end]
        points.append({
            "at": begin,
            "arrivals": sum(begin <= token.created_at < end for token in tokens),
            "served": sum(token.status == "completed" and begin <= token.ended_at < end for token in tokens),
            "averageWait": average_minutes(waits),
            "queueLength": None if begin > now else sum(token.created_at <= boundary and (token.started_at is None or token.started_at > boundary) and (token.ended_at is None or token.ended_at > boundary) for token in tokens),
        })
    return {
        "days": days,
        "waiting": sum(token.status == "waiting" for token in tokens),
        "inService": sum(token.status == "serving" for token in tokens),
        "servedToday": sum(token.status == "completed" and today <= token.ended_at <= now for token in tokens),
        "completed": len(completed),
        "arrivals": sum(since <= token.created_at <= now for token in tokens),
        "cancelled": sum(token.status == "cancelled" and since <= token.ended_at <= now for token in tokens),
        "averageWait": average_minutes([token.started_at - token.created_at for token in started]),
        "averageService": average_minutes([token.ended_at - token.started_at for token in completed]),
        "longestWait": max([0, *((now - token.created_at) // MINUTE for token in tokens if token.status == "waiting")]),
        "points": points,
        "breakdown": [{
            "id": str(queue.id), "name": queue.name, "color": queue.color, "waiting": queue.waiting,
            "served": sum(token.queue_id == queue.id for token in completed),
            "averageWait": average_minutes([token.started_at - token.created_at for token in started if token.queue_id == queue.id]),
        } for queue in queues],
    }


def activity(manager, params):
    queryset = Token.objects.filter(queue__manager=manager).select_related("queue").annotate(event_at=Coalesce("ended_at", "started_at", "created_at"))
    queue_id = params.get("queueId")
    if queue_id:
        try:
            queue_id = uuid.UUID(queue_id)
        except (ValueError, TypeError):
            raise APIError(404, "Queue not found.")
        owned_queue(manager, queue_id)
        queryset = queryset.filter(queue_id=queue_id)
    before = integer_parameter(params.get("before"), 9_007_199_254_740_991, "activity cursor")
    if before <= 0 or before > 9_007_199_254_740_991:
        raise APIError(400, "Invalid activity cursor.")
    condition = Q(event_at__lt=before)
    if params.get("beforeId"):
        try:
            before_id = uuid.UUID(params["beforeId"])
        except (ValueError, TypeError):
            raise APIError(400, "Invalid activity cursor.")
        condition |= Q(event_at=before, id__lt=before_id)
    return [{**token_data(token), "queue_name": token.queue.name, "prefix": token.queue.prefix, "color": token.queue.color, "event_at": token.event_at}
            for token in queryset.filter(condition).order_by("-event_at", "-id")[:100]]


@transaction.atomic
def create_demo():
    now = timestamp_ms()
    Manager.objects.filter(is_demo=True, created_at__lt=now - 7 * DAY).delete()
    manager = Manager.objects.create_user(email=f"demo-{uuid.uuid4()}@queueflow.local", name="Alex Morgan", is_demo=True)
    names = ["Olivia Bennett", "Liam Carter", "Emma Wilson", "Noah Williams", "Amelia Brooks", "Elijah Davis", "Sophia Martinez", "James Anderson", "Isabella Taylor", "Lucas Thompson", "Mia Robinson", "Henry Walker"]
    for qi, name in enumerate(["General reception", "Account services", "Priority support"]):
        queue = create_queue(manager, {"name": name})
        queue.created_at = now + qi
        rows = []
        number = 1
        for ago in range(6, -1, -1):
            count = [13, 19, 16, 24, 21, 28, 18][6 - ago] + qi * 3
            for i in range(count):
                # Keep every sample service fully in the past at any hour.
                created = now - ago * DAY - (count - i + 8) * 20 * MINUTE
                started = created + (4 + (i * 3 + qi) % 14) * MINUTE
                cancelled = i % 13 == 12
                rows.append(Token(queue=queue, number=number, name=names[(i + qi) % len(names)], status="cancelled" if cancelled else "completed", position=i + 1, created_at=created, started_at=None if cancelled else started, ended_at=started + (3 + i % 5) * MINUTE))
                number += 1
        rows.append(Token(queue=queue, number=number, name=names[qi + 3], note="General enquiry", status="serving", position=0, created_at=now - 18 * MINUTE, started_at=now - (2 + qi) * MINUTE))
        number += 1
        for i in range([6, 4, 3][qi]):
            rows.append(Token(queue=queue, number=number, name=names[(i + qi) % len(names)], note=["Account enquiry", "Document collection", "", "New registration"][i % 4], position=i + 1, created_at=now - (19 - i * 3) * MINUTE))
            number += 1
        Token.objects.bulk_create(rows)
        queue.next_number = number
        queue.save(update_fields=["next_number", "created_at"])
    return manager
