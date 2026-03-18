# backend/ai_services/segmenter_service.py

"""
Segmenter Service using PyTorch DeepLabV3
Provides real object segmentation for pet-ifying images
"""

import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models.segmentation as segmentation_models
import numpy as np
import cv2
from pathlib import Path
from PIL import Image
import io
import base64
import logging
import traceback
from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

class SegmenterService:
    """
    Service class for image segmentation using PyTorch DeepLabV3
    Uses a pretrained model to segment objects from images
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_model()
        return cls._instance
    
    def _load_model(self):
        """Load the pretrained DeepLabV3 model"""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.transform = None
        
        print("\n" + "="*60)
        print("LOADING PYTORCH SEGMENTATION MODEL")
        print("="*60)
        
        try:
            # Load pretrained DeepLabV3 with ResNet50 backbone
            print("Loading DeepLabV3-ResNet50 model...")
            self.model = segmentation_models.deeplabv3_resnet50(pretrained=True)
            self.model = self.model.to(self.device)
            self.model.eval()
            
            # Define image transformations
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((256, 256)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                   std=[0.229, 0.224, 0.225])
            ])
            
            print(f"Model loaded successfully on {self.device}")
            print(f"   Model type: DeepLabV3-ResNet50")
            print(f"   Input size: 256x256")
            print(f"   Number of classes: 21 (COCO classes)")
            
            # Test the model
            self._test_model()
            
        except Exception as e:
            print(f"Failed to load model: {e}")
            traceback.print_exc()
            self.model = None
    
    def _test_model(self):
        """Test the model with dummy input"""
        try:
            print("\n🧪 Testing model with dummy input...")
            dummy_input = torch.randn(1, 3, 256, 256).to(self.device)
            
            with torch.no_grad():
                output = self.model(dummy_input)['out']
            
            print(f"   Test passed!")
            print(f"   Output shape: {output.shape}")
            print(f"   Output range: [{output.min():.3f}, {output.max():.3f}]")
            
        except Exception as e:
            print(f"Test failed: {e}")
            traceback.print_exc()
    
    def preprocess_image(self, image):
        """
        Preprocess an image for the model
        Args:
            image: Can be path (str/Path), PIL Image, numpy array, or Django UploadedFile
        Returns:
            tuple: (preprocessed tensor, original size)
        """
        # Load image based on input type
        if isinstance(image, (str, Path)):
            # Path to image file
            img = cv2.imread(str(image))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            original_size = (img.shape[1], img.shape[0])  # (width, height)
            
        elif isinstance(image, Image.Image):
            # PIL Image
            img = np.array(image)
            original_size = (img.shape[1], img.shape[0])
            
        elif isinstance(image, InMemoryUploadedFile):
            # Django uploaded file
            image_bytes = image.read()
            img = Image.open(io.BytesIO(image_bytes))
            img = np.array(img)
            original_size = (img.shape[1], img.shape[0])
            
        elif isinstance(image, np.ndarray):
            # Numpy array
            img = image
            original_size = (img.shape[1], img.shape[0])
            
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
        
        # Apply transformations
        img_tensor = self.transform(img).unsqueeze(0).to(self.device)
        
        return img_tensor, original_size
    
    def segment(self, image, target_class=None, confidence_threshold=0.5):
        """
        Segment an image and return a binary mask
        Args:
            image: Input image (various formats supported)
            target_class: Specific COCO class to segment (None = any object)
            confidence_threshold: Minimum confidence for mask pixels
        Returns:
            tuple: (binary mask as numpy array, overlay image)
        """
        print(f"\nSegmenting image...")
        
        if self.model is None:
            print("Model not loaded, using fallback mask")
            return self._get_fallback_mask(image)
        
        try:
            # Preprocess
            input_tensor, original_size = self.preprocess_image(image)
            print(f"   Input tensor shape: {input_tensor.shape}")
            
            # Run inference
            with torch.no_grad():
                output = self.model(input_tensor)['out']
                print(f"   Raw output shape: {output.shape}")
            
            # Convert to probabilities and get class predictions
            probabilities = torch.softmax(output, dim=1)[0]
            predicted_classes = output.argmax(dim=1)[0]
            
            # Move to CPU and convert to numpy
            predicted_classes = predicted_classes.cpu().numpy()
            probabilities = probabilities.cpu().numpy()
            
            print(f"Predicted classes shape: {predicted_classes.shape}")
            print(f"Unique classes found: {np.unique(predicted_classes)}")
            
            # Create binary mask based on target class
            if target_class is not None:
                # Mask only the target class
                class_mask = (predicted_classes == target_class)
                # Apply confidence threshold
                class_confidence = probabilities[target_class]
                mask = (class_mask & (class_confidence > confidence_threshold)).astype(np.uint8) * 255
            else:
                # Mask any non-background class (class 0 is background in COCO)
                mask = (predicted_classes > 0).astype(np.uint8) * 255
                # Optional: Apply confidence threshold
                if confidence_threshold > 0:
                    max_probs = probabilities.max(axis=0)
                    mask = mask & (max_probs > confidence_threshold)
                    mask = mask.astype(np.uint8) * 255
            
            print(f"   Mask unique values: {np.unique(mask)}")
            print(f"   Mask sum (white pixels): {np.sum(mask > 0)}")
            
            # Resize mask back to original size
            mask = cv2.resize(mask, original_size)
            
            # Create overlay
            overlay = self._create_overlay(image, mask)
            
            return mask, overlay
            
        except Exception as e:
            print(f"Error in segmentation: {e}")
            traceback.print_exc()
            return self._get_fallback_mask(image)
    
    def segment_with_class_names(self, image, class_names=None):
        """
        Segment an image and return masks for specific class names
        Args:
            image: Input image
            class_names: List of class names (e.g., ['dog', 'cat', 'person'])
        Returns:
            dict: {class_name: mask}
        """
        # COCO class names (index 0 is background)
        COCO_CLASSES = [
            '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
            'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
            'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag',
            'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
            'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana',
            'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
            'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'dining table',
            'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
            'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock',
            'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]
        
        if self.model is None:
            print("Model not loaded")
            return {}
        
        try:
            # Preprocess
            input_tensor, _ = self.preprocess_image(image)
            
            # Run inference
            with torch.no_grad():
                output = self.model(input_tensor)['out']
            
            # Get predicted classes
            predicted_classes = output.argmax(dim=1)[0].cpu().numpy()
            
            # Create masks for requested classes
            result = {}
            if class_names:
                for class_name in class_names:
                    if class_name in COCO_CLASSES:
                        class_idx = COCO_CLASSES.index(class_name)
                        mask = (predicted_classes == class_idx).astype(np.uint8) * 255
                        result[class_name] = mask
            else:
                # Return all non-background classes
                for class_idx in range(1, len(COCO_CLASSES)):
                    if np.any(predicted_classes == class_idx):
                        mask = (predicted_classes == class_idx).astype(np.uint8) * 255
                        result[COCO_CLASSES[class_idx]] = mask
            
            return result
            
        except Exception as e:
            print(f"Error in class segmentation: {e}")
            return {}
    
    def _create_overlay(self, image, mask, color=(0, 255, 0), alpha=0.3):
        """Create an overlay of the mask on the image"""
        # Load image based on input type
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif isinstance(image, Image.Image):
            img = np.array(image)
        elif isinstance(image, InMemoryUploadedFile):
            image_bytes = image.read()
            img = Image.open(io.BytesIO(image_bytes))
            img = np.array(img)
        else:
            img = image.copy()
        
        # Create overlay
        overlay = img.copy()
        
        # Create colored mask
        colored_mask = np.zeros_like(img)
        colored_mask[mask > 0] = color
        
        # Blend
        overlay = cv2.addWeighted(overlay, 1, colored_mask, alpha, 0)
        
        return overlay
    
    def _get_fallback_mask(self, image):
        """Return a fallback mask (circle) when model fails"""
        print("Using fallback circle mask")
        
        # Get image dimensions
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            h, w = img.shape[:2]
        elif isinstance(image, Image.Image):
            w, h = image.size
        elif isinstance(image, InMemoryUploadedFile):
            image_bytes = image.read()
            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size
        else:
            h, w = image.shape[:2]
        
        # Create circular mask
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        radius = min(h, w) // 3
        cv2.circle(mask, center, radius, 255, -1)
        
        # Create simple overlay
        overlay = self._create_overlay(image, mask)
        
        return mask, overlay
    
    def create_transparent_cutout(self, image, mask):
        """Create a PNG with transparency from image and mask"""
        # Load image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif isinstance(image, Image.Image):
            img = np.array(image)
        else:
            img = image.copy()
        
        # Create RGBA image
        if len(img.shape) == 3 and img.shape[2] == 3:
            rgba = np.dstack([img, mask])
        else:
            rgba = cv2.cvtColor(img, cv2.COLOR_RGB2RGBA)
            rgba[:, :, 3] = mask
        
        return rgba
    
    def process_upload(self, uploaded_file, output_dir=None):
        """
        Process an uploaded image file
        Args:
            uploaded_file: Django InMemoryUploadedFile
            output_dir: Optional output directory
        Returns:
            dict: Paths to generated images
        """
        import uuid
        from django.conf import settings
        from datetime import datetime
        
        # Generate unique ID
        session_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Set up paths
        if output_dir is None:
            media_root = Path(settings.MEDIA_ROOT)
            output_dir = media_root / 'segmented' / f"{timestamp}_{session_id}"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing upload to: {output_dir}")
        
        # Save original
        original_path = output_dir / 'original.jpg'
        with open(original_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        print(f"   Original saved: {original_path}")
        
        # Segment the image
        mask, overlay = self.segment(original_path)
        
        # Save mask
        mask_path = output_dir / 'mask.png'
        cv2.imwrite(str(mask_path), mask)
        print(f"   Mask saved: {mask_path}")
        
        # Save overlay
        overlay_path = output_dir / 'overlay.png'
        overlay_bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(overlay_path), overlay_bgr)
        print(f"   Overlay saved: {overlay_path}")
        
        # Create and save transparent cutout
        cutout = self.create_transparent_cutout(original_path, mask)
        cutout_path = output_dir / 'cutout.png'
        cv2.imwrite(str(cutout_path), cv2.cvtColor(cutout, cv2.COLOR_RGBA2BGRA))
        print(f"   Cutout saved: {cutout_path}")
        
        # Create relative paths for Django
        rel_path = f"segmented/{timestamp}_{session_id}"
        
        result = {
            'session_id': session_id,
            'original': f"{rel_path}/original.jpg",
            'mask': f"{rel_path}/mask.png",
            'overlay': f"{rel_path}/overlay.png",
            'cutout': f"{rel_path}/cutout.png",
        }
        
        print(f"Processing complete!")
        return result


# Singleton instance
_segmenter_service = None

def get_segmenter_service():
    """Get or create the singleton segmenter service instance"""
    global _segmenter_service
    if _segmenter_service is None:
        _segmenter_service = SegmenterService()
    return _segmenter_service