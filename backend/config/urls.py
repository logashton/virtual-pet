from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("auth/", TemplateView.as_view(template_name="auth.html"), name="auth"),
    path("pets/", TemplateView.as_view(template_name="pets.html"), name="pets"),
    path("mod/", TemplateView.as_view(template_name="mod.html"), name="mod"),
    path("manage/", TemplateView.as_view(template_name="manage.html"), name="manage"),
    path("api/auth/", include("core.urls")),
    path("api/pets/", include("core.pets_urls")),
    path("api/moderation-reports/", include("core.moderation_urls")),
    path("api/admin/", include("core.admin_urls")),
    path("chat/", include("chat.urls")),
    path("admin/", admin.site.urls),
    path("pets/<int:pet_id>/chat/", TemplateView.as_view(template_name="pet_chat.html"), name="pet_chat"),
    path("api/pets/", include("core.stats_urls")),
    path("pets/create/", TemplateView.as_view(template_name="create_pet.html"), name="pet_create"),
    
    
]




