"""
Example: Load and use the fine-tuned pet chatbot
"""

from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from peft import PeftModel, PeftConfig
import torch

# Method 1: Load LoRA weights onto base model
def load_lora_model(model_path="models/pet_chatbot/lora_weights"):
  # Load base model
  base_model = AutoModelForCausalLM.from_pretrained(
    "distilgpt2",
    device_map="auto",
    torch_dtype=torch.float16
  )

  # Load tokenizer
  tokenizer = AutoTokenizer.from_pretrained(model_path)

  # Load LoRA weights
  model = PeftModel.from_pretrained(base_model, model_path)
  model = model.merge_and_unload()  # Merge LoRA weights into base model

  return model, tokenizer

# Method 2: If you saved the full model
def load_full_model(model_path="models/pet_chatbot"):
  model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    torch_dtype=torch.float16
  )
  tokenizer = AutoTokenizer.from_pretrained(model_path)
  return model, tokenizer

# Generate a response
def chat_with_pet(model, tokenizer, prompt, max_length=100):
  inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

  with torch.no_grad():
    outputs = model.generate(
      **inputs,
      max_length=max_length,
      temperature=0.7,
      top_p=0.9,
      do_sample=True,
      pad_token_id=tokenizer.pad_token_id,
      eos_token_id=tokenizer.eos_token_id
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response

# Example usage
if __name__ == "__main__":
  model, tokenizer = load_lora_model()

  prompt = "### Instruction:\nYou are a playful puppy.\n\n### Input:\nWant to play fetch?\n\n### Response:"
  response = chat_with_pet(model, tokenizer, prompt)
  print(response)
