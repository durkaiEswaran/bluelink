from django.urls import path
from . import views

urlpatterns = [
    # Health
    path('health/', views.health_check, name='health_check'),

    # Admin auth
    path('admin/login/', views.admin_login, name='admin_login'),

    # User CRUD (all admin-protected except login)
    path('users/', views.list_users, name='list_users'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/login/', views.user_login, name='user_login'),
    path('users/<int:user_id>/', views.get_user, name='get_user'),
    path('users/<int:user_id>/update/', views.update_user, name='update_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('users/<int:user_id>/status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/<int:user_id>/change-password/', views.change_password, name='change_password'),
     # NEW — reset device binding so user can login from a different phone
    path('users/<int:user_id>/reset-device/', views.reset_device, name='reset_device'),
]
