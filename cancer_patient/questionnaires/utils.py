# questionnaires/utils.py

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed

def verify_admin(user):
    """Verify that the user has admin role"""
    if not user.is_authenticated:
        raise AuthenticationFailed("Authentication required")
    
    # Check if user has admin role
    if hasattr(user, 'role') and user.role == 'ADMIN':
        return True
    
    # Alternative: Check if user is staff or superuser
    if user.is_staff or user.is_superuser:
        return True
    
    raise PermissionDenied("Admin access required")