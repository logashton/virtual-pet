from django.urls import path
from . import views
from core.views_segmenter import SegmentImageView

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("api/", views.pet_chat_api, name="chat_api_legacy"),
    path("api/<int:pet_id>/", views.pet_chat_api, name="pet_chat_api"),
    path("api/<int:pet_id>/summarize/", views.summarize_now, name="pet_chat_summarize"),
    path("api/<int:pet_id>/summary/", views.summary_detail, name="pet_chat_summary_detail"),
    path("personality/", views.get_personality, name="get_personality"),
    path("personality/<int:pet_id>/", views.pet_personality_view, name="pet_personality"),
    path("api/remove-background/", SegmentImageView.as_view(), name="remove_background"),
]