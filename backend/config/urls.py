from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from core import web_views
from core.views_background import RemoveBackgroundView
from core.views_image_to_3d import ImageTo3DView
from core.views_generate_personality import GeneratePersonalityView


urlpatterns = [
    path("", web_views.home_page, name="home"),
    path("search/", web_views.pets_search_page, name="pets_search"),
    path("auth/", web_views.auth_page, name="auth"),
    path("logout/", web_views.logout_page, name="logout"),
    path("pets/", web_views.pets_page, name="pets"),
    path("mod/", web_views.mod_page, name="mod"),
    path("manage/", web_views.manage_page, name="manage"),
    path("api/auth/", include("core.urls")),
    path("api/pets/", include("core.pets_urls")),
    path("api/moderation-reports/", include("core.moderation_urls")),
    path("api/admin/", include("core.admin_urls")),
    path("api/remove-background/", RemoveBackgroundView.as_view(), name="remove_background"),
    path("api/image-to-3d/", ImageTo3DView.as_view(), name="image_to_3d"),
    path("api/generate-personality/", GeneratePersonalityView.as_view(), name="generate_personality"),  #generate personality from image
    path("chat/", include("chat.urls")),
    path("admin/", admin.site.urls),
    path("pets/<int:pet_id>/chat/", web_views.pet_chat_page, name="pet_chat"),
    path("api/pets/", include("core.stats_urls")),
    path("pets/create/", web_views.create_pet_page, name="pet_create"),
    path("pets/create-3d/", web_views.pet_creator_3d_page, name="pet_creator_3d"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)