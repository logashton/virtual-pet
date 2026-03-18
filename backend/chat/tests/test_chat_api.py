"""Tests for chat API: GET history, POST message. Mocks external LLM requests."""
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ChatMessage, ChatSession, Pet, PetStats, User


def fake_llm_response():
    return {
        "choices": [
            {
                "message": {
                    "content": '{"reply": "Hello! *wags tail*", "stat_changes": {"happiness": 5, "energy": -2, "hunger": -1, "cleanliness": 0, "health": 0}}'
                }
            }
        ]
    }


class ChatApiTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="chat@test.com",
            username="chatuser",
            password="p",
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name="TestPet",
            visibility=Pet.Visibility.PUBLIC,
        )
        PetStats.objects.get_or_create(pet=self.pet)

    def test_get_history_unauthenticated_returns_empty(self):
        resp = self.client.get(f"/chat/api/{self.pet.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data.get("session_id"))
        self.assertEqual(resp.data.get("messages"), [])

    def test_get_history_authenticated_returns_session_and_messages(self):
        session = ChatSession.objects.create(pet=self.pet, user=self.owner)
        ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.USER, content="Hi")
        ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.PET, content="Hi back")
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(f"/chat/api/{self.pet.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["session_id"], session.id)
        self.assertEqual(len(resp.data["messages"]), 2)

    def test_get_history_private_pet_as_stranger_404(self):
        self.pet.visibility = Pet.Visibility.PRIVATE
        self.pet.save()
        other = User.objects.create_user(email="o@o.com", username="other", password="p")
        self.client.force_authenticate(user=other)
        resp = self.client.get(f"/chat/api/{self.pet.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("chat.views.requests.post")
    def test_post_message_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = fake_llm_response()
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(
            f"/chat/api/{self.pet.id}/",
            {"message": "Hello!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("reply", resp.data)
        self.assertIn("Hello!", resp.data["reply"])
        self.assertIn("stat_changes", resp.data)
        self.assertEqual(resp.data["session_id"], ChatSession.objects.get(pet=self.pet, user=self.owner).id)
        self.assertEqual(ChatMessage.objects.filter(session__pet=self.pet).count(), 2)

    def test_post_message_requires_message_body(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(f"/chat/api/{self.pet.id}/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_pet_not_found(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get("/chat/api/99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
