from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("auth/", TemplateView.as_view(template_name="auth.html"), name="auth"),
    path("pets/", TemplateView.as_view(template_name="pets.html"), name="pets"),
    path("api/auth/", include("core.urls")),
    path("api/pets/", include("core.pets_urls")),
    path("chat/", include("chat.urls")),
    path("admin/", admin.site.urls),
]




