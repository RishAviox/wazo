from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Custom permission to only allow access to admin/staff users.
    """
    def has_permission(self, request, view):
        try:
            return bool(request.user and request.user.is_authenticated and request.user.is_staff)
        except:
            False