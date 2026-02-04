from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("api/", views.chat_api, name="chat_api"),
    path("personality/", views.get_personality, name="get_personality"),
]