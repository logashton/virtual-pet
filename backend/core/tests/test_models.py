"""Tests for core models: User, Pet, PetAsset, PetStats, PetPersonality."""
from django.test import TestCase

from core.models import Pet, PetAsset, PetPersonality, PetStats, User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="secret123",
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("secret123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            username="admin",
            password="admin123",
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class PetModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            username="owner",
            password="pass",
        )

    def test_create_pet(self):
        pet = Pet.objects.create(
            owner=self.owner,
            name="Fluffy",
            visibility=Pet.Visibility.PUBLIC,
        )
        self.assertEqual(pet.name, "Fluffy")
        self.assertEqual(pet.visibility, Pet.Visibility.PUBLIC)
        self.assertEqual(pet.owner_id, self.owner.id)


class PetAssetModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="a@b.com",
            username="u",
            password="p",
        )
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_create_image_asset(self):
        asset = PetAsset.objects.create(
            pet=self.pet,
            original_image_url="/media/foo.jpg",
            asset_type=PetAsset.AssetType.IMAGE,
            status=PetAsset.Status.READY,
        )
        self.assertEqual(asset.asset_type, PetAsset.AssetType.IMAGE)
        self.assertIsNone(asset.model_3d_url)

    def test_create_3d_asset(self):
        asset = PetAsset.objects.create(
            pet=self.pet,
            original_image_url="",
            model_3d_url="/media/pet.glb",
            asset_type=PetAsset.AssetType.MODEL_3D,
            status=PetAsset.Status.READY,
        )
        self.assertEqual(asset.asset_type, PetAsset.AssetType.MODEL_3D)
        self.assertEqual(asset.model_3d_url, "/media/pet.glb")


class PetStatsModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="s@t.com",
            username="u",
            password="p",
        )
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_pet_stats_created_with_defaults(self):
        stats = PetStats.objects.create(pet=self.pet)
        self.assertEqual(stats.hunger, 50)
        self.assertEqual(stats.energy, 50)
        self.assertEqual(stats.health, 100)
        self.assertEqual(stats.level, 1)


class PetPersonalityModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="p@q.com",
            username="u",
            password="p",
        )
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_create_personality(self):
        p = PetPersonality.objects.create(
            pet=self.pet,
            roleplay_prompt="Backstory: A rock.",
            traits={"list": ["curious", "lazy"]},
            tone="snarky",
        )
        self.assertEqual(p.pet_id, self.pet.id)
        self.assertIn("curious", p.traits.get("list", []))
