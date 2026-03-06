from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging
import traceback
from bson import ObjectId

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data['success'] = False
        response.data['status_code'] = response.status_code
    else:
        logger.error(f"Unhandled exception: {str(exc)}")
        logger.error(traceback.format_exc())
        
        data = {
            'success': False,
            'error': 'Internal server error',
            'message': str(exc) if context.get('request') and context['request'].user.is_staff else 'Something went wrong'
        }
        response = Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response

class APIError(Exception):
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST, errors=None):
        self.message = message
        self.status_code = status_code
        self.errors = errors or {}
        super().__init__(self.message)

def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            return Response({
                'success': False,
                'error': e.message,
                'errors': e.errors
            }, status=e.status_code)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return wrapper

def validate_mongodb_id(id_value):
    try:
        return ObjectId(id_value)
    except:
        raise APIError("Invalid ID format", status_code=status.HTTP_400_BAD_REQUEST)