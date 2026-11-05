from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    path("config", views.config),
    path("auth/register", views.register),
    path("auth/login", views.sign_in),
    path("auth/logout", views.sign_out),
    path("auth/demo", views.demo),
    path("auth/me", views.me),
    path("queues", views.queues),
    path("queues/<uuid:queue_id>", views.queue_detail),
    path("queues/<uuid:queue_id>/tokens", views.add_token),
    path("queues/<uuid:queue_id>/serve-next", views.serve_next),
    path("queues/<uuid:queue_id>/tokens/<uuid:token_id>/move", views.move_token),
    path("queues/<uuid:queue_id>/tokens/<uuid:token_id>/cancel", views.finish_token, {"action": "cancel"}),
    path("queues/<uuid:queue_id>/tokens/<uuid:token_id>/complete", views.finish_token, {"action": "complete"}),
    path("analytics", views.analytics),
    path("activity", views.activity),
]
