# backend/chat/views_segmenter.py

"""
Views for image segmentation endpoints
"""

import json
import traceback
from pathlib import Path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

print("LOADING VIEWS_SEGMENTER.PY")

# Import the segmenter service
try:
    from .services.segmenter_service import get_segmenter_service
    print("Successfully imported segmenter_service")
    segmenter = get_segmenter_service()
    print(f"Segmenter loaded: {segmenter is not None}")
except Exception as e:
    print(f"Failed to load segmenter: {e}")
    traceback.print_exc()
    segmenter = None


@api_view(['POST'])
@csrf_exempt
def segment_image(request):
    """
    Endpoint for image segmentation
    Expects: multipart/form-data with 'image' file
    Returns: JSON with paths to segmented images
    """
    print(f"\nSEGMENT_IMAGE VIEW CALLED")
    print(f"Request method: {request.method}")
    print(f"Request FILES keys: {list(request.FILES.keys())}")
    
    try:
        # Check if image was uploaded
        if 'image' not in request.FILES:
            print("No image in request.FILES")
            return Response(
                {'success': False, 'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['image']
        print(f"File received: {uploaded_file.name}")
        print(f"File size: {uploaded_file.size} bytes")
        print(f"Content type: {uploaded_file.content_type}")
        
        # Validate file type
        if not uploaded_file.content_type.startswith('image/'):
            print(f"Invalid content type: {uploaded_file.content_type}")
            return Response(
                {'success': False, 'error': 'File must be an image'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if segmenter is available
        if segmenter is None:
            print("Segmenter is not available")
            return Response(
                {'success': False, 'error': 'Segmentation service unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Process the image
        print("Processing image with segmenter...")
        result = segmenter.process_upload(uploaded_file)
        print(f"Processing complete: {result}")
        
        # Add full URLs for frontend
        base_url = request.build_absolute_uri('/media/')
        result['original_url'] = base_url + result['original']
        result['mask_url'] = base_url + result['mask']
        result['overlay_url'] = base_url + result['overlay']
        result['cutout_url'] = base_url + result['cutout']
        
        return Response({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        print(f"Exception in segment_image: {e}")
        traceback.print_exc()
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def segment_base64(request):
    """
    Alternative endpoint that accepts base64 encoded image
    Expects: JSON with 'image' field containing base64 string
    """
    print(f"\nSEGMENT_BASE64 VIEW CALLED")
    
    try:
        # Parse JSON request
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {'success': False, 'error': 'Invalid JSON'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_data = data.get('image', '')
        target_class = data.get('class', None)
        
        if not image_data:
            return Response(
                {'success': False, 'error': 'No image data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Decode base64
        import base64
        import uuid
        from datetime import datetime
        from django.core.files.base import ContentFile
        from io import BytesIO
        from PIL import Image
        
        # Remove header if present
        if ';base64,' in image_data:
            format, imgstr = image_data.split(';base64,')
            ext = format.split('/')[-1]
        else:
            imgstr = image_data
            ext = 'jpg'
        
        # Decode and create image
        decoded = base64.b64decode(imgstr)
        img = Image.open(BytesIO(decoded))
        
        # Create a temporary file
        temp_dir = Path(settings.MEDIA_ROOT) / 'temp'
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"temp_{uuid.uuid4().hex[:8]}.{ext}"
        img.save(temp_path)
        
        # Segment the image
        if segmenter and target_class:
            # Get specific class mask
            masks = segmenter.segment_with_class_names(temp_path, [target_class])
            mask = masks.get(target_class, np.zeros((img.height, img.width), dtype=np.uint8))
        elif segmenter:
            # Get general object mask
            mask, _ = segmenter.segment(temp_path)
        else:
            mask, _ = segmenter._get_fallback_mask(temp_path) if segmenter else None
        
        # Clean up temp file
        temp_path.unlink()
        
        # Convert mask to base64 for response
        mask_img = Image.fromarray(mask)
        mask_buffer = BytesIO()
        mask_img.save(mask_buffer, format='PNG')
        mask_base64 = base64.b64encode(mask_buffer.getvalue()).decode()
        
        return Response({
            'success': True,
            'mask_base64': mask_base64,
        })
        
    except Exception as e:
        print(f"Exception in segment_base64: {e}")
        traceback.print_exc()
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def segmenter_status(request):
    """Check if segmenter is loaded and ready"""
    status_info = {
        'loaded': segmenter is not None and segmenter.model is not None,
        'device': str(segmenter.device) if segmenter else None,
        'model_type': 'DeepLabV3-ResNet50' if segmenter and segmenter.model else None,
    }
    
    if segmenter and segmenter.model:
        status_info['status'] = 'ready'
    elif segmenter:
        status_info['status'] = 'model_not_loaded'
    else:
        status_info['status'] = 'service_unavailable'
    
    return Response(status_info)


@api_view(['POST'])
@csrf_exempt
def segment_with_class(request):
    """
    Segment image and return masks for specific classes
    Expects: multipart/form-data with 'image' file and 'classes' JSON field
    """
    try:
        if 'image' not in request.FILES:
            return Response(
                {'success': False, 'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get requested classes
        classes_json = request.POST.get('classes', '[]')
        try:
            class_names = json.loads(classes_json)
        except:
            class_names = []
        
        uploaded_file = request.FILES['image']
        
        if segmenter is None:
            return Response(
                {'success': False, 'error': 'Segmentation service unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Save temporary file
        import uuid
        from datetime import datetime
        from pathlib import Path
        
        temp_dir = Path(settings.MEDIA_ROOT) / 'temp'
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"temp_{uuid.uuid4().hex[:8]}.jpg"
        with open(temp_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        
        # Get masks for requested classes
        masks = segmenter.segment_with_class_names(temp_path, class_names)
        
        # Clean up
        temp_path.unlink()
        
        # Convert masks to base64
        result = {}
        for class_name, mask in masks.items():
            mask_img = Image.fromarray(mask)
            buffer = BytesIO()
            mask_img.save(buffer, format='PNG')
            result[class_name] = base64.b64encode(buffer.getvalue()).decode()
        
        return Response({
            'success': True,
            'masks': result
        })
        
    except Exception as e:
        print(f"Exception in segment_with_class: {e}")
        traceback.print_exc()
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )