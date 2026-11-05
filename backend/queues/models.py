import time
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


def timestamp_ms():
    return time.time_ns() // 1_000_000


class ManagerAccountManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superusers must have is_staff=True and is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class Manager(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Legacy scrypt encodings exceed Django's default 128-character column.
    # SQLite didn't enforce that limit; PostgreSQL correctly does.
    password = models.CharField("password", max_length=256)
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=80)
    is_demo = models.BooleanField(default=False)
    created_at = models.BigIntegerField(default=timestamp_ms)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    objects = ManagerAccountManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="manager_email_case_insensitive")]

    def __str__(self):
        return self.name or self.email


class Queue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE, related_name="queues")
    name = models.CharField(max_length=60)
    prefix = models.CharField(max_length=3)
    color = models.CharField(max_length=7, default="#7960e9")
    paused = models.BooleanField(default=False)
    next_number = models.PositiveIntegerField(default=1)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.BigIntegerField(default=timestamp_ms)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.name


class Token(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        SERVING = "serving", "In service"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name="tokens")
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=80)
    note = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    position = models.PositiveIntegerField()
    created_at = models.BigIntegerField(default=timestamp_ms)
    started_at = models.BigIntegerField(null=True, blank=True)
    ended_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["queue", "number"], name="unique_queue_token_number"),
            models.UniqueConstraint(fields=["queue"], condition=models.Q(status="serving"), name="one_service_per_queue"),
            models.CheckConstraint(condition=models.Q(status__in=["waiting", "serving", "completed", "cancelled"]), name="valid_token_status"),
        ]
        indexes = [
            models.Index(fields=["queue", "status", "position"], name="token_queue_status_position"),
            models.Index(fields=["created_at"], name="token_created_at"),
        ]

    def __str__(self):
        return f"{self.queue.prefix}-{self.number:03d} · {self.name}"


class RateLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    resets_at = models.BigIntegerField()
