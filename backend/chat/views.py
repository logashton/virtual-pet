# backend/chat/views.py
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response    
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import json
import requests

from core.models import temp_personality
from core.serializer import Temp_PersonalitySerializer

# Import ONLY from chatbot_service, not the other way around
from .services.chatbot_service import get_chatbot_service

# PET PERSONALITY (Static for now)
PET_PERSONALITY = "You are Rocko, a playful and energetic virtual pet Rock. You love to fetch, play, and cuddle with your owner. Or, try to at least. Because you're a rock. You have a friendly and enthusiastic personality, always eager to please and make your owner happy."

HUGGINGFACE_API_TOKEN = ""  # replace with actual token
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}

# Initializes the chatbot once
print("Initializing chatbot")
chatbot = get_chatbot_service()

def chat_page(request):
    return render(request, "chat.html")

#testing 
@api_view(['GET'])
def get_personality(request):
    return Response(Temp_PersonalitySerializer({'prompt': PET_PERSONALITY}).data)

@api_view(['POST'])
@csrf_exempt
def chat_api(request):
    """Handles chat messages"""
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        pet_state = data.get("pet_state", {})
        
        if not user_message:
            return JsonResponse({"reply": "Please say something!"}, status=400)
        
        # Tries with the custom model first
        if chatbot.model is not None:
            reply = chatbot.generate_response(user_message, pet_state)
            return JsonResponse({
                "reply": reply,
                "personality": PET_PERSONALITY,
                "model_type": "custom"
            })
        
        # Fallback to the Hugging Face API
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
            return JsonResponse({"error": "API error"}, status=500)
        
        output = response.json()
        reply = output.get("choices", [{}])[0].get("message", {}).get("content", "...")
        
        return JsonResponse({
            "reply": reply,
            "personality": PET_PERSONALITY,
            "model_type": "api"
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

'''
Code by Rahul

Commented out because my brain was not working properly while writing this part and I needed a clean slate

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
'''