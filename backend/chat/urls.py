from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("api/", views.pet_chat_api, name="chat_api_legacy"),
    path("api/<int:pet_id>/", views.pet_chat_api, name="pet_chat_api"),
    path("personality/", views.get_personality, name="get_personality"),
    path("personality/<int:pet_id>/", views.pet_personality_view, name="pet_personality"),
]