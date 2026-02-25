from django.urls import path

from . import views_pets, views_personality

urlpatterns = [
    path("", views_pets.PetListCreateView.as_view(), name="pet_list_create"),
    path("<int:pk>/", views_pets.PetDetailView.as_view(), name="pet_detail"),
    path("<int:pk>/upload/", views_pets.PetUploadView.as_view(), name="pet_upload"),
    path("<int:pk>/personality/", views_personality.PetPersonalityView.as_view(), name="pet_personality"),
]
