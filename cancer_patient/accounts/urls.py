from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('refresh-token/', views.refresh_token, name='refresh_token'),
    path('logout/', views.logout, name='logout'),
    
    # Profile
    path('profile/', views.get_profile, name='get_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Admin
    path('users/<str:user_type>/', views.get_users_by_type, name='get_users_by_type'),
]