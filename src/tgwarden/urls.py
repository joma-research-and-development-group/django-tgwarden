"""URL configuration for tgwarden."""

from django.urls import path

from tgwarden import views

app_name = "tgwarden"

urlpatterns = [
    path("health/", views.health, name="health"),
]
