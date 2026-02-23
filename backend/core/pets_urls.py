from django.urls import path

from . import views_pets

urlpatterns = [
    path("", views_pets.PetListCreateView.as_view(), name="pet_list_create"),
    path("<int:pk>/", views_pets.PetDetailView.as_view(), name="pet_detail"),
]
