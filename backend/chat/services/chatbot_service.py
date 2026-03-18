
# CHATBOT SERVICE
# Handles the actual chatbot communications

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import logging
import traceback

logger = logging.getLogger(__name__)

class PetChatbotService:
    def __init__(self, model_path=None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.tokenizer = None
        self.model_path = Path(model_path) if model_path else None
        
        print("Starting chatbot...")
        
        self.load_model()
    
    def load_model(self):
        # Loads the model and handles any mismatch of covab
        try:
            # Always loads the tokenizer from base model first (in case of incompatabilities)
            print()
            print("1. Loading tokenizer from base model...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                "distilgpt2",
                use_fast=False
            )
            
            # Adds a padding token if needed
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                print("   Added pad_token")
            
            print(f"Tokenizer loaded successfully. Vocab size: {len(self.tokenizer)}")
            
            # Loads the base model
            print()
            print("2. Loading base model...")
            base_model = AutoModelForCausalLM.from_pretrained(
                "distilgpt2",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            self.model = base_model
            
            # Tries to load LoRA weights if they exist
            if self.model_path and self.model_path.exists():
                print()
                print(f"3. Looking for adapter_config.json in: {self.model_path}")
                
                # Finds the checkpoint folder (checkpoint-3) or lora_weights
                possible_config_paths = [
                    self.model_path / 'adapter_config.json',
                    self.model_path / 'checkpoint-3' / 'adapter_config.json',
                    self.model_path / 'lora_weights' / 'adapter_config.json',
                    self.model_path / 'checkpoint-3' / 'lora_weights' / 'adapter_config.json',
                ]
                
                adapter_config_path = None
                for path in possible_config_paths:
                    if path.exists():
                        adapter_config_path = path
                        print(f"Found adapter_config.json at: {path}")
                        break
                
                if adapter_config_path:
                    # Gets the directory containing the adapter config
                    lora_folder = adapter_config_path.parent
                    
                    try:
                        print(f"Loading LoRA weights from {lora_folder}...")
                        
                        from peft import PeftModel
                        
                        # Loads the LoRA weights. Automatically handles any inconsistent vocab
                        self.model = PeftModel.from_pretrained(
                            base_model,
                            lora_folder,
                            is_trainable=False
                        )
                        
                        print("LoRA weights loaded successfully")
                        
                        # Merges the weights for faster inference
                        print("Merging LoRA weights...")
                        self.model = self.model.merge_and_unload()
                        print("LoRA weights merged")
                        
                    except Exception as e:
                        print(f"WARNING! Could not load LoRA weights: {e}")
                        print("Attempting manual weight loading...")
                        
                        # This only loads compatible weights
                        try:
                            from safetensors.torch import load_file
                            import json
                            
                            # Loads the adapter config
                            with open(adapter_config_path, 'r') as f:
                                adapter_config = json.load(f)
                            
                            # Finds the safetensors file
                            safetensors_files = list(lora_folder.glob('*.safetensors'))
                            if safetensors_files:
                                state_dict = load_file(str(safetensors_files[0]))
                                
                                # Filters out incompatible weights
                                filtered_state_dict = {}
                                for key, value in state_dict.items():
                                    # Skips lm_head and wte weights
                                    if 'lm_head' in key or 'wte' in key:
                                        print(f"      Skipping {key} due to vocabulary mismatch")
                                        continue
                                    
                                    # Remove base_model.model prefix if present
                                    if key.startswith('base_model.model.'):
                                        new_key = key.replace('base_model.model.', '', 1)
                                    else:
                                        new_key = key
                                    
                                    filtered_state_dict[new_key] = value
                                
                                # Creates a new PEFT model
                                from peft import LoraConfig, get_peft_model
                                
                                lora_config = LoraConfig(
                                    r=adapter_config.get('r', 8),
                                    lora_alpha=adapter_config.get('lora_alpha', 32),
                                    target_modules=adapter_config.get('target_modules', ['c_attn', 'c_proj', 'c_fc']),
                                    lora_dropout=adapter_config.get('lora_dropout', 0.1),
                                    bias=adapter_config.get('bias', 'none'),
                                    task_type="CAUSAL_LM"
                                )
                                
                                self.model = get_peft_model(base_model, lora_config)
                                self.model.load_state_dict(filtered_state_dict, strict=False)
                                self.model = self.model.merge_and_unload()
                                print(f"Manually loaded {len(filtered_state_dict)} weights")
                        except Exception as manual_error:
                            print(f"Manual loading also failed: {manual_error}")
                            self.model = base_model
                else:
                    print("No adapter_config.json found, using base model")
            
            # Moves the model to device
            self.model = self.model.to(self.device)
            self.model.eval()
            
            print()
            print(f"Chatbot service ready on {self.device}")
            if self.model_path and self.model_path.exists():
                print(f"   Loaded from: {self.model_path}")
            
        except Exception as e: # In case of failure
            print(f"Failed to load model: {e}")
            traceback.print_exc()
            self.model = None
            self.tokenizer = None
    
    def generate_response(self, user_message, pet_state=None):
        # Handles the actual response generation
        if self.model is None or self.tokenizer is None:
            return self._get_fallback_response()
        
        try:
            # Simple prompt. Should be updated later
            if pet_state:
                prompt = f"You are a {pet_state.get('species', 'pet')} named {pet_state.get('name', 'Pet')}. {user_message}"
            else:
                prompt = f"You are a friendly pet. {user_message}"
            
            # Tokenize process
            inputs = self.tokenizer.encode(prompt, return_tensors='pt').to(self.device)
            
            # Generate process
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=50,
                    temperature=0.8,
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            # Decoding process
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Removes the prompt from the response
            response = response[len(prompt):].strip()
            
            return response if response else self._get_fallback_response()
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return self._get_fallback_response()
    
    def _get_fallback_response(self):
        import random
        responses = [
            "*wags tail happily*",
            "*purrs softly*",
            "*makes a happy sound*",
            "*nuzzles against you*",
            "*looks at you with big eyes*"
        ]
        return random.choice(responses)

# Singleton instance
_chatbot_service = None

def get_chatbot_service(model_path=None):
    global _chatbot_service
    if _chatbot_service is None:
        # If there's no model path provided, tries to find it in standard locations
        if model_path is None:
            base_dir = Path(__file__).parent.parent
            pet_chatbot_dir = base_dir / 'ai_models' / 'pet_chatbot'
            
            print(f"Looking for models in: {pet_chatbot_dir}")
            
            if pet_chatbot_dir.exists():
                # Finds all subdirectories that look like timestamps (e.g., 20260223_175055)
                model_folders = []
                for item in pet_chatbot_dir.iterdir():
                    if item.is_dir():
                        # Check if it's a timestamp folder (starts with numbers)
                        if item.name[0].isdigit():
                            model_folders.append(item)
                        # Also checks if it has lora_weights inside
                        elif (item / 'lora_weights').exists():
                            model_folders.append(item)
                
                if model_folders:
                    # Sorts by name (which would be the timestamp) and gets the most recent version
                    model_folders.sort(reverse=True)
                    latest_model = model_folders[0]
                    
                    print(f"Found model folders:")
                    for folder in model_folders:
                        marker = "✓" if folder == latest_model else " "
                        print(f"  {marker} {folder.name}")
                    
                    # Checks if lora_weights folder exists inside the latest model folder
                    lora_path = latest_model / 'lora_weights'
                    if lora_path.exists():
                        model_path = str(lora_path)
                        print(f"\nUsing LoRA weights from: {lora_path}")
                    else:
                        model_path = str(latest_model)
                        print(f"\nUsing model from: {latest_model}")
                else:
                    print("No timestamp folders found, checking for direct lora_weights...")
                    # Checks for lora_weights directly in pet_chatbot dir
                    lora_direct = pet_chatbot_dir / 'lora_weights'
                    if lora_direct.exists():
                        model_path = str(lora_direct)
                        print(f"Found lora_weights at: {lora_direct}")
                    else:
                        print("No model found, will use base model")
            else:
                print(f"Directory not found: {pet_chatbot_dir}")
        
        _chatbot_service = PetChatbotService(model_path)
    return _chatbot_service