from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response    
from rest_framework import status
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import json

from core.models import temp_personality
from core.serializer import Temp_PersonalitySerializer
import requests
import os


# PET PERSONALITY (Static for now)
PET_PERSONALITY = "You are Rocko, a playful and energetic virtual pet dog. You love to fetch, play, and cuddle with your owner. You have a friendly and enthusiastic personality, always eager to please and make your owner happy."

HUGGINGFACE_API_TOKEN = ""  # replace with actual token

HF_API_URL = "https://router.huggingface.co/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"
}


def chat_page(request):
    return render(request, "chat.html")

#testing 
@api_view(['GET'])
def get_personality(request):
    return Response(Temp_PersonalitySerializer({'prompt': PET_PERSONALITY}).data)
    

@api_view(['POST'])
@csrf_exempt
def chat_api(request):
    """Handles chat messages and returns Hugging Face model responses."""
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        if not user_message:
            return JsonResponse({"reply": "Please say something!"}, status=400)

        # Build the chat prompt using the pet personality
        messages = [
            {"role": "system", "content": PET_PERSONALITY},
            {"role": "user", "content": user_message}
        ]

        payload = {
            "model": "deepseek-ai/DeepSeek-V3.2:novita",
            "messages": messages,
            "parameters": {"max_new_tokens": 150}
        }

        response = requests.post(HF_API_URL, headers=HEADERS, json=payload, timeout=20)

        if response.status_code != 200:
            return JsonResponse({"error": "Hugging Face API error", "details": response.text}, status=500)

        output = response.json()

        # Process response
        try:
            reply = output["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            reply = "Rocko is thinking... but can't respond right now."

        return JsonResponse({
            "reply": reply,
            "personality": PET_PERSONALITY
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"error": "Hugging Face API request failed", "details": str(e)}, status=500)
