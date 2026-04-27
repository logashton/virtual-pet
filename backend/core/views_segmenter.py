# backend/core/views_segmenter.py

from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import traceback
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class SegmentImageView(View):
    # The API endpoint for image segmentation stuff. The POST is upload image, return back mask, overlay, and cutout
    
    def post(self, request):
        print("\n" + "="*60)
        print("SEGMENTATION API CALLED")
        print("="*60)
        
        try:
            # Logs request info
            print(f"Request method: {request.method}")
            print(f"Request FILES keys: {list(request.FILES.keys())}")
            print(f"Request POST keys: {list(request.POST.keys())}")
            
            # Checks if the image was uploaded
            if 'image' not in request.FILES:
                print("No image was found in request.FILES")
                return JsonResponse({
                    'success': False,
                    'error': 'No image provided'
                }, status=400)
            
            uploaded_file = request.FILES['image']
            print(f"Received file: {uploaded_file.name}")
            print(f"File size: {uploaded_file.size} bytes")
            print(f"Content type: {uploaded_file.content_type}")
            
            # Validates the file type
            if not uploaded_file.content_type.startswith('image/'):
                print(f"Invalid file type: {uploaded_file.content_type}")
                return JsonResponse({
                    'success': False,
                    'error': 'File must be an image'
                }, status=400)
            
            # Tries to import and use the segmenter service
            print("\nImporting segmenter service...")
            try:
                from chat.services.segmenter_service import get_segmenter_service
                print("Successfully imported get_segmenter_service")
            except ImportError as import_err:
                print(f"Import error: {import_err}")
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'error': f'Import error: {str(import_err)}'
                }, status=500)
            
            print("\nGetting segmenter service instance...")
            try:
                segmenter = get_segmenter_service()
                print("Segmenter service obtained")
            except Exception as service_err:
                print(f"Service error: {service_err}")
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'error': f'Segmenter service error: {str(service_err)}'
                }, status=500)
            
            print("\nProcessing upload...")
            try:
                result = segmenter.process_upload(uploaded_file)
                print(f"Processing complete")
                print(f"Session ID: {result.get('session_id')}")
                print(f"Original: {result.get('original')}")
                print(f"Mask: {result.get('mask')}")
                print(f"Overlay: {result.get('overlay')}")
                print(f"Cutout: {result.get('cutout')}")
            except Exception as process_err:
                print(f"Processing error: {process_err}")
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'error': f'Processing error: {str(process_err)}'
                }, status=500)
            
            # Builds the full URLs for the frontend
            base_url = request.build_absolute_uri(settings.MEDIA_URL)
            if not base_url.endswith('/'):
                base_url += '/'
            
            response_data = {
                'success': True,
                'data': {
                    'session_id': result['session_id'],
                    'original_url': base_url + result['original'],
                    'mask_url': base_url + result['mask'],
                    'overlay_url': base_url + result['overlay'],
                    'cutout_url': base_url + result['cutout'],
                    'original': result['original'],
                    'mask': result['mask'],
                    'overlay': result['overlay'],
                    'cutout': result['cutout'],
                }
            }
            
            print("\nSending success response")
            return JsonResponse(response_data)
            
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def get(self, request):
        # GET returns the service info
        return JsonResponse({
            'service': 'Image Segmenter',
            'status': 'active',
            'endpoints': {
                'POST': '/api/segment/ - Upload image for segmentation'
            }
        })