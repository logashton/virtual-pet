# backend/chat/services/chatbot_service.py

"""
CHATBOT SERVICE - Returns both response and stat changes
"""

import torch
from transformers import AutoModelForCausalLM, LlamaTokenizer
from pathlib import Path
import logging
import traceback
import random
import re
import json
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PetChatbotService:
    # Service class for generating pet responses using a local LLM
    
    def __init__(self, model_path: Optional[str] = None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.tokenizer = None
        self.model_path = Path(model_path) if model_path else None
        
        print("Starting Chatbot Service...")
        print(f"Device: {self.device}")
        
        self.load_model()
    
    def _find_model_path(self) -> Optional[Path]:
        # Automatically finds the model path
        
        if self.model_path and self.model_path.exists():
            return self.model_path
        
        backend_root = Path(__file__).parent.parent.parent
        
        search_paths = [
            backend_root / 'chat' / 'ai_models' / 'pet_chatbot' / 'primary-model',
            backend_root / 'ai_models' / 'pet_chatbot' / 'primary-model',
            Path('./chat/ai_models/pet_chatbot/primary-model'),
            Path('./ai_models/pet_chatbot/primary-model'),
        ]
        
        print("\nSearching for model...")
        for path in search_paths:
            if path.exists() and (path / 'config.json').exists():
                print(f"Found at: {path}")
                return path
        
        return None
    
    def load_model(self):
        # Loads the local model and tokenizer
        
        actual_path = self._find_model_path()
        
        if actual_path is None:
            print("\nNo model found.")
            self.model = None
            self.tokenizer = None
            return
        
        self.model_path = actual_path
        
        try:
            print(f"\nLoading model from: {self.model_path}")
            
            # Load tokenizer
            print("\n1. Loading tokenizer...")
            self.tokenizer = LlamaTokenizer.from_pretrained(
                str(self.model_path),
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.padding_side = "right"
            
            print(f"Tokenizer loaded. Vocab size: {len(self.tokenizer)}")
            
            # Loads model
            print("\n2. Loading model...")
            
            if torch.cuda.is_available():
                print("   GPU mode (float16)")
                self.model = AutoModelForCausalLM.from_pretrained(
                    str(self.model_path),
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )
            else:
                print("CPU mode (float32)")
                self.model = AutoModelForCausalLM.from_pretrained(
                    str(self.model_path),
                    torch_dtype=torch.float32,
                    trust_remote_code=True
                )
                self.model = self.model.to(self.device)
            
            self.model.eval()
            
            print("Chatbot service ready!")
            print(f"Device: {self.device}")
            
        except Exception as e:
            print(f"\nFailed to load model: {e}")
            traceback.print_exc()
            self.model = None
            self.tokenizer = None

    def generate_response(self, user_message, pet_state=None, system_prompt=None):
        # Generates a response from the pet (returns just the text for backward compatibility)

        response, _ = self.generate_response_with_stats(user_message, pet_state, system_prompt)
        return response
    
    def generate_response_with_stats(
        self, 
        user_message: str, 
        pet_state: Optional[Dict[str, Any]] = None, 
        system_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Generate a response AND stat changes based on the interaction
        
        Returns:
            Tuple of (response_text, stat_changes_dict)
        """
        
        # Fallback if the model not loaded
        if self.model is None or self.tokenizer is None:
            return self._get_fallback_response(user_message), self._get_default_stat_changes(user_message)
        
        try:
            pet_name = pet_state.get('name', 'Pet') if pet_state else 'Pet'
            
            # Build prompt that asks for JSON response with stat changes
            system_content = system_prompt if system_prompt else f"""You are {pet_name}, a friendly pet.
When responding, you MUST output valid JSON in this exact format:
{{
  "reply": "your response here with *actions*",
  "stat_changes": {{
    "hunger": integer (-20 to 20),
    "energy": integer (-20 to 20),
    "happiness": integer (-20 to 20),
    "cleanliness": integer (-20 to 20),
    "health": integer (-20 to 20)
  }}
}}

IMPORTANT STAT GUIDELINES:
- HUNGER: High number = full/not hungry, Low number = hungry/starving
- ENERGY: High number = energetic/awake, Low number = tired/sleepy
- HAPPINESS: High number = happy, Low number = sad
- CLEANLINESS: High number = clean, Low number = dirty
- HEALTH: High number = healthy, Low number = sick

How stats should change:
- Feeding the pet: hunger INCREASES (becomes fuller), happiness increases slightly
- Playing: happiness increases, energy DECREASES (gets tired), hunger DECREASES slightly (gets hungrier)
- Petting: happiness increases
- Bath: cleanliness INCREASES
- Sleeping: energy INCREASES
- Being ignored: happiness DECREASES

Most changes should be between -10 and +10.
Only include stats that actually change (value != 0)."""
            
            # Use ChatML format
            prompt = f"""<|im_start|>system
{system_content}<|im_end|>
<|im_start|>user
{user_message}<|im_end|>
<|im_start|>assistant
"""
            
            print(f"\n💬 Generating with stats...")
            print(f"   User: {user_message[:50]}...")
            
            # Encode
            inputs = self.tokenizer.encode(
                prompt, 
                return_tensors='pt',
                truncation=True,
                max_length=512
            )
            
            if inputs.numel() == 0:
                return self._get_fallback_response(user_message), self._get_default_stat_changes(user_message)
            
            inputs = inputs.to(self.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=150,  # Need more tokens for JSON
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode
            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=False)
            
            # Extract assistant response
            response_text = self._extract_assistant_response(full_response)
            
            # Try to parse JSON from response
            reply, stat_changes = self._parse_json_response(response_text)
            
            # If no valid JSON, use fallback with default stats
            if stat_changes is None or not stat_changes:
                reply = response_text if response_text else self._get_fallback_response(user_message)
                stat_changes = self._get_default_stat_changes(user_message, reply)
            
            print(f"   Response: {reply[:80]}...")
            print(f"   Stat changes: {stat_changes}")
            
            return reply, stat_changes
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            return self._get_fallback_response(user_message), self._get_default_stat_changes(user_message)
    
    def _parse_json_response(self, response: str) -> Tuple[str, Dict[str, int]]:
        # Parses JSON from the model response
        
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*"reply"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
                reply = data.get('reply', response)
                stat_changes = data.get('stat_changes', {})
                
                # Validate stat changes
                valid_stats = {}
                for stat in ['hunger', 'energy', 'happiness', 'cleanliness', 'health']:
                    if stat in stat_changes:
                        value = int(stat_changes[stat])
                        # Clamp between -20 and 20
                        value = max(-20, min(20, value))
                        if value != 0:
                            valid_stats[stat] = value
                
                return reply, valid_stats
            
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"   JSON parse error: {e}")
        
        return response, None
    
    def _extract_assistant_response(self, full_response: str) -> str:
        # Extract only the assistant's response 
        
        patterns = [
            r'<\|im_start\|>assistant\n(.*?)(?:<\|im_end\|>|$)',
            r'Assistant:\s*(.*?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_response, re.DOTALL)
            if match:
                response = match.group(1).strip()
                response = re.sub(r'<\|.*?\|>', '', response)
                return response
        
        if '<|im_start|>assistant' in full_response:
            parts = full_response.split('<|im_start|>assistant', 1)
            if len(parts) > 1:
                response = parts[1].strip()
                response = re.sub(r'<\|im_end\|>.*$', '', response)
                return response
        
        return full_response.strip()
    
    def _get_default_stat_changes(self, user_message: str, response: str = "") -> Dict[str, int]:
        # Generate default stat changes based on message content
        
        stat_changes = {}
        msg_lower = user_message.lower()
        
        # FEEDING - increases hunger (makes fuller), increases happiness
        if any(word in msg_lower for word in ['feed', 'food', 'eat', 'treat', 'meal', 'feed', 'dinner', 'breakfast', 'lunch', 'snack']):
            stat_changes['hunger'] = 12      # +12 = fuller (less hungry)
            stat_changes['happiness'] = 8
            stat_changes['energy'] = 3
        
        # PLAYING - increases happiness, decreases energy
        elif any(word in msg_lower for word in ['play', 'fetch', 'toy', 'ball', 'run', 'chase', 'walk']):
            stat_changes['happiness'] = 10
            stat_changes['energy'] = -8      # -8 = more tired
            stat_changes['hunger'] = -3      # -3 = hungrier from playing
        
        # PETTING/AFFECTION - increases happiness
        elif any(word in msg_lower for word in ['pet', 'cuddle', 'hug', 'love', 'good', 'sweet', 'nice', 'pat']):
            stat_changes['happiness'] = 8
        
        # BATH/CLEANING - increases cleanliness
        elif any(word in msg_lower for word in ['bath', 'clean', 'wash', 'groom', 'shower']):
            stat_changes['cleanliness'] = 20
            stat_changes['happiness'] = 5
            stat_changes['energy'] = -5      # Baths can be tiring
        
        # SLEEP/REST - increases energy, decreases hunger slightly
        elif any(word in msg_lower for word in ['sleep', 'nap', 'rest', 'bed', 'tired', 'sleepy']):
            stat_changes['energy'] = 15
            stat_changes['hunger'] = -4      # -4 = hungrier after sleeping
        
        # MEDICINE/HEALING - increases health
        elif any(word in msg_lower for word in ['heal', 'medicine', 'doctor', 'vet', 'cure']):
            stat_changes['health'] = 15
            stat_changes['happiness'] = -3   # Doesn't like medicine
        
        # NEGATIVE interactions
        elif any(word in msg_lower for word in ['ignore', 'bad', 'stupid', 'hate', 'mean', 'rude']):
            stat_changes['happiness'] = -10
            stat_changes['energy'] = -3
        
        # DEFAULT - small happiness increase for kind interactions
        else:
            stat_changes['happiness'] = 3
        
        return stat_changes
    
    def _get_fallback_response(self, user_message: str = "") -> str:
        # Returns a context-appropriate fallback response
        
        msg_lower = user_message.lower()
        
        if "feed" in msg_lower or "food" in msg_lower:
            return random.choice([
                "*eats happily* Thank you! That was delicious!",
                "*purrs while eating* Mmm, so good!",
            ])
        elif "play" in msg_lower:
            return random.choice([
                "*wags tail excitedly* Let's play!",
                "*bounces around* Yay! Playtime!",
            ])
        elif "sleep" in msg_lower:
            return random.choice([
                "*yawns* Goodnight... *curls up*",
                "*gets cozy* Sleepy time... zzz",
            ])
        elif "bath" in msg_lower or "clean" in msg_lower:
            return random.choice([
                "*splashes happily* This feels nice!",
                "*purrs* I feel so clean now!",
            ])
        else:
            return random.choice([
                "*tilts head* That's nice!",
                "*purrs softly* I like that!",
                "*wags tail* Tell me more!",
            ])


# Singleton
_chatbot_service = None


def get_chatbot_service(model_path: Optional[str] = None) -> PetChatbotService:
    global _chatbot_service
    if _chatbot_service is None:
        _chatbot_service = PetChatbotService(model_path)
    return _chatbot_service


if __name__ == "__main__":
    chatbot = get_chatbot_service()
    if chatbot.model:
        response = chatbot.generate_response("Hello!", {'name': 'Buddy'})
        print(f"\nResponse: {response}")
    else:
        print("\nModel not loaded")