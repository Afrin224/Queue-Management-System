from django.contrib import admin
from django.urls import include, path, re_path

from queues import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("queues.urls")),
    path("", views.index, name="index"),
    re_path(r"^api/.*$", views.api_not_found),
]

handler404 = "queues.views.not_found"
handler500 = "queues.views.server_error"
