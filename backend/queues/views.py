"""JSON endpoints matching the frontend's API contract."""
import json
import logging
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, OperationalError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe

from . import services
from .models import Manager
from .services import APIError

logger = logging.getLogger(__name__)


def api_endpoint(*methods, public=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                if request.method not in methods:
                    response = JsonResponse({"error": "Method not allowed."}, status=405)
                    response.headers["Allow"] = ", ".join(methods)
                    return response
                if not public and not request.user.is_authenticated:
                    raise APIError(401, "Please sign in to continue.")
                request.json = {}
                if request.method not in ["GET", "HEAD"]:
                    if request.headers.get("Sec-Fetch-Site") == "cross-site":
                        raise APIError(403, "Cross-site requests are not allowed.")
                    if request.content_type != "application/json":
                        raise APIError(415, "Requests must use application/json.")
                    if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                        raise APIError(413, "Request is too large.")
                    try:
                        request.json = json.loads(request.body)
                    except (ValueError, UnicodeDecodeError):
                        raise APIError(400, "Please send a valid JSON object.")
                    if not isinstance(request.json, dict):
                        raise APIError(400, "Please send a valid JSON object.")
                return view(request, *args, **kwargs)
            except APIError as error:
                return JsonResponse({"error": str(error)}, status=error.status)
            except RequestDataTooBig:
                return JsonResponse({"error": "Request is too large."}, status=413)
            except OperationalError:
                logger.exception("Database operation failed")
                return JsonResponse({"error": "The workspace is busy. Please try again."}, status=503)
        return wrapped
    return decorate


def credentials(body, registration=False):
    email = services.text_field(body.get("email"), "Email", 254).lower()
    try:
        validate_email(email)
    except ValidationError:
        raise APIError(400, "Enter a valid email address.")
    password = body.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise APIError(400, "Use a password between 8 and 256 characters.")
    data = {"email": email, "password": password}
    if registration:
        data["name"] = services.text_field(body.get("name"), "Your name", 80)
    return data


@ensure_csrf_cookie
@require_safe
def index(request):
    return render(request, "index.html")


@ensure_csrf_cookie
@api_endpoint("GET", public=True)
def config(request):
    return JsonResponse({"demoEnabled": settings.ENABLE_DEMO, "backend": "django"})


@api_endpoint("GET", public=True)
def health(request):
    return JsonResponse({"status": "ok", "backend": "django"})


@api_endpoint("POST", public=True)
def register(request):
    services.throttle(request.META.get("REMOTE_ADDR", ""), "auth")
    data = credentials(request.json, registration=True)
    if Manager.objects.filter(email__iexact=data["email"]).exists():
        raise APIError(409, "An account with this email already exists. Please sign in.")
    manager = Manager(email=data["email"], name=data["name"])
    manager.set_password(data["password"])
    try:
        with transaction.atomic():
            manager.save()
    except IntegrityError:
        raise APIError(409, "An account with this email already exists. Please sign in.")
    login(request, manager)
    return JsonResponse({"user": services.user_data(manager)}, status=201)


@api_endpoint("POST", public=True)
def sign_in(request):
    services.throttle(request.META.get("REMOTE_ADDR", ""), "auth")
    data = credentials(request.json)
    manager = authenticate(request, email=data["email"], password=data["password"])
    if manager is None or manager.is_demo:
        raise APIError(401, "Email or password is incorrect.")
    login(request, manager)
    return JsonResponse({"user": services.user_data(manager)})


@api_endpoint("POST", public=True)
def demo(request):
    if not settings.ENABLE_DEMO:
        raise APIError(404, "Demo workspaces are disabled.")
    services.throttle(request.META.get("REMOTE_ADDR", ""), "demo")
    manager = services.create_demo()
    login(request, manager)
    return JsonResponse({"user": services.user_data(manager)}, status=201)


@api_endpoint("GET")
def me(request):
    return JsonResponse({"user": services.user_data(request.user)})


@api_endpoint("POST")
def sign_out(request):
    logout(request)
    return JsonResponse({"success": True})


@api_endpoint("GET", "POST")
def queues(request):
    if request.method == "GET":
        return JsonResponse({"queues": [services.queue_data(queue) for queue in services.list_queues(request.user)]})
    queue = services.create_queue(request.user, request.json)
    return JsonResponse({"queue": services.queue_data(queue)}, status=201)


@api_endpoint("GET", "PATCH")
def queue_detail(request, queue_id):
    if request.method == "GET":
        return JsonResponse(services.queue_details(request.user, queue_id))
    services.patch_queue(request.user, queue_id, request.json)
    return JsonResponse({"success": True})


@api_endpoint("POST")
def add_token(request, queue_id):
    token = services.add_token(request.user, queue_id, request.json)
    return JsonResponse({"token": services.token_data(token)}, status=201)


@api_endpoint("POST")
def move_token(request, queue_id, token_id):
    services.move_token(request.user, queue_id, token_id, request.json)
    return JsonResponse({"success": True})


@api_endpoint("POST")
def serve_next(request, queue_id):
    token = services.serve_next(request.user, queue_id, request.json)
    return JsonResponse({"token": services.token_data(token)})


@api_endpoint("POST")
def finish_token(request, queue_id, token_id, action):
    services.finish_token(request.user, queue_id, token_id, action)
    return JsonResponse({"success": True})


@api_endpoint("GET")
def analytics(request):
    return JsonResponse(services.analytics(request.user, request.GET))


@api_endpoint("GET")
def activity(request):
    return JsonResponse({"activity": services.activity(request.user, request.GET)})


def csrf_failure(request, reason=""):
    return JsonResponse({"error": "Your security token is missing or expired. Reload the page and try again."}, status=403)


def api_not_found(request):
    return JsonResponse({"error": "API route not found."}, status=404)


def not_found(request, exception=None):
    return JsonResponse({"error": "Page not found."}, status=404)


def server_error(request):
    return JsonResponse({"error": "Something went wrong. Please try again."}, status=500)
