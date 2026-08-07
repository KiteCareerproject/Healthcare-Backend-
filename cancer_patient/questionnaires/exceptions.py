# questionnaires/exceptions.py

from rest_framework import status
from rest_framework.exceptions import APIException

class APIError(APIException):
    """Custom API Exception"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An error occurred'
    default_code = 'error'
    
    def __init__(self, detail=None, status_code=None):
        if status_code:
            self.status_code = status_code
        if detail:
            self.detail = detail
        else:
            self.detail = self.default_detail