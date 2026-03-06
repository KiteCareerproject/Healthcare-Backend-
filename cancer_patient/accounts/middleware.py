import traceback
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        logger.error(f"Unhandled Exception: {str(exception)}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': 'Internal server error',
            'message': str(exception) if settings.DEBUG else 'Something went wrong'
        }, status=500)