"""Tests for pets API: list, create, detail, update, delete, upload, upload-model, personality, stats."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Pet, PetAsset, PetPersonality, PetStats, User


class PetsListCreateTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="u@example.com",
            username="user1",
            password="pass",
        )

    def test_list_mine_requires_auth(self):
        resp = self.client.get("/api/pets/?scope=mine")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_mine_returns_own_pets(self):
        Pet.objects.create(owner=self.user, name="A", visibility=Pet.Visibility.PRIVATE)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/pets/?scope=mine")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "A")

    def test_list_public_unauthenticated(self):
        Pet.objects.create(
            owner=self.user,
            name="Public",
            visibility=Pet.Visibility.PUBLIC,
        )
        resp = self.client.get("/api/pets/?scope=public")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_create_pet_requires_auth(self):
        resp = self.client.post(
            "/api/pets/",
            {"name": "New", "visibility": "private"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_pet_success(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            "/api/pets/",
            {"name": "NewPet", "visibility": "public"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "NewPet")
        self.assertEqual(resp.data["visibility"], "public")
        self.assertTrue(Pet.objects.filter(owner=self.user, name="NewPet").exists())
        self.assertTrue(PetStats.objects.filter(pet__name="NewPet").exists())


class PetDetailTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="o@o.com", username="owner", password="p")
        self.other = User.objects.create_user(email="x@x.com", username="other", password="p")
        self.pet_private = Pet.objects.create(
            owner=self.owner,
            name="Private",
            visibility=Pet.Visibility.PRIVATE,
        )
        self.pet_public = Pet.objects.create(
            owner=self.owner,
            name="Public",
            visibility=Pet.Visibility.PUBLIC,
        )

    def test_get_private_pet_as_owner(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(f"/api/pets/{self.pet_private.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Private")

    def test_get_private_pet_as_stranger_returns_404(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(f"/api/pets/{self.pet_private.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_public_pet_unauthenticated(self):
        resp = self.client.get(f"/api/pets/{self.pet_public.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_patch_pet_as_owner(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(
            f"/api/pets/{self.pet_private.id}/",
            {"name": "Updated", "visibility": "unlisted"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.pet_private.refresh_from_db()
        self.assertEqual(self.pet_private.name, "Updated")
        self.assertEqual(self.pet_private.visibility, Pet.Visibility.UNLISTED)

    def test_delete_pet_as_owner(self):
        self.client.force_authenticate(user=self.owner)
        pid = self.pet_private.id
        resp = self.client.delete(f"/api/pets/{pid}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Pet.objects.filter(pk=pid).exists())


class PetUploadTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="o@o.com", username="owner", password="p")
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_upload_image_success(self):
        self.client.force_authenticate(user=self.owner)
        f = SimpleUploadedFile("photo.jpg", b"fake image bytes", content_type="image/jpeg")
        resp = self.client.post(f"/api/pets/{self.pet.id}/upload/", {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("original_image_url", resp.data)
        self.assertTrue(
            PetAsset.objects.filter(pet=self.pet, asset_type=PetAsset.AssetType.IMAGE).exists()
        )

    def test_upload_image_missing_file(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(f"/api/pets/{self.pet.id}/upload/", {}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PetUploadModelTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="o@o.com", username="owner", password="p")
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_upload_model_glb_success(self):
        self.client.force_authenticate(user=self.owner)
        f = SimpleUploadedFile("model.glb", b"fake glb bytes", content_type="model/gltf-binary")
        resp = self.client.post(
            f"/api/pets/{self.pet.id}/upload-model/",
            {"model": f},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("model_3d_url", resp.data)
        asset = PetAsset.objects.get(pet=self.pet, asset_type=PetAsset.AssetType.MODEL_3D)
        self.assertTrue(asset.model_3d_url.endswith(".glb") or ".glb" in asset.model_3d_url)

    def test_upload_model_obj_success(self):
        self.client.force_authenticate(user=self.owner)
        f = SimpleUploadedFile("model.obj", b"v 0 0 0\nf 1 2 3", content_type="text/plain")
        resp = self.client.post(
            f"/api/pets/{self.pet.id}/upload-model/",
            {"model": f},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PetAsset.objects.filter(pet=self.pet, asset_type=PetAsset.AssetType.MODEL_3D).exists()
        )

    def test_upload_model_rejects_invalid_extension(self):
        self.client.force_authenticate(user=self.owner)
        f = SimpleUploadedFile("file.txt", b"data", content_type="text/plain")
        resp = self.client.post(
            f"/api/pets/{self.pet.id}/upload-model/",
            {"model": f},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PetPersonalityTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="o@o.com", username="owner", password="p")
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)

    def test_patch_personality_creates_and_updates(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(
            f"/api/pets/{self.pet.id}/personality/",
            {
                "self_concept": "a rock",
                "tone": "snarky",
                "traits": ["curious", "lazy"],
                "roleplay_prompt": "Backstory: I am a rock.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        p = PetPersonality.objects.get(pet=self.pet)
        self.assertEqual(p.traits.get("self_concept"), "a rock")
        self.assertEqual(p.tone, "snarky")
        self.assertEqual(set(p.traits.get("list", [])), {"curious", "lazy"})
        self.assertIn("rock", p.roleplay_prompt)


class PetStatsTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="o@o.com", username="owner", password="p")
        self.pet = Pet.objects.create(owner=self.owner, name="P", visibility=Pet.Visibility.PRIVATE)
        PetStats.objects.get_or_create(pet=self.pet)

    def test_get_stats(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(f"/api/pets/{self.pet.id}/stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("hunger", resp.data)
        self.assertIn("energy", resp.data)
        self.assertIn("health", resp.data)
