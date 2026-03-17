"""Tests for web_views helpers used in templates: _pet_card_data (has_3d, image_url)."""
from django.test import TestCase

from core.models import Pet, PetAsset, PetPersonality, User
from core.web_views import _pet_card_data


class PetCardDataTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="c@d.com",
            username="carduser",
            password="p",
        )

    def test_card_data_has_3d_when_3d_asset_exists(self):
        pet = Pet.objects.create(
            owner=self.owner,
            name="3DPet",
            visibility=Pet.Visibility.PUBLIC,
        )
        PetAsset.objects.create(
            pet=pet,
            original_image_url="",
            model_3d_url="/media/pet.glb",
            asset_type=PetAsset.AssetType.MODEL_3D,
            status=PetAsset.Status.READY,
        )
        data = _pet_card_data(pet)
        self.assertTrue(data["has_3d"])
        self.assertIsNone(data["image_url"])

    def test_card_data_has_3d_and_image_when_both_assets(self):
        pet = Pet.objects.create(
            owner=self.owner,
            name="Both",
            visibility=Pet.Visibility.PUBLIC,
        )
        PetAsset.objects.create(
            pet=pet,
            original_image_url="/media/photo.jpg",
            asset_type=PetAsset.AssetType.IMAGE,
            status=PetAsset.Status.READY,
        )
        PetAsset.objects.create(
            pet=pet,
            original_image_url="",
            model_3d_url="/media/model.glb",
            asset_type=PetAsset.AssetType.MODEL_3D,
            status=PetAsset.Status.READY,
        )
        data = _pet_card_data(pet)
        self.assertTrue(data["has_3d"])
        self.assertEqual(data["image_url"], "/media/photo.jpg")

    def test_card_data_image_from_any_asset_order(self):
        """has_3d and image_url are set correctly regardless of asset order."""
        pet = Pet.objects.create(
            owner=self.owner,
            name="Order",
            visibility=Pet.Visibility.PUBLIC,
        )
        PetAsset.objects.create(
            pet=pet,
            original_image_url="/media/first.jpg",
            asset_type=PetAsset.AssetType.IMAGE,
            status=PetAsset.Status.READY,
        )
        PetAsset.objects.create(
            pet=pet,
            original_image_url="",
            model_3d_url="/media/m.glb",
            asset_type=PetAsset.AssetType.MODEL_3D,
            status=PetAsset.Status.READY,
        )
        data = _pet_card_data(pet)
        self.assertTrue(data["has_3d"])
        self.assertEqual(data["image_url"], "/media/first.jpg")

    def test_card_data_description_from_personality(self):
        pet = Pet.objects.create(
            owner=self.owner,
            name="Desc",
            visibility=Pet.Visibility.PUBLIC,
        )
        PetPersonality.objects.create(
            pet=pet,
            roleplay_prompt="Backstory: A wise old cactus.",
            traits={},
        )
        data = _pet_card_data(pet)
        self.assertIn("wise old cactus", data["description"])
