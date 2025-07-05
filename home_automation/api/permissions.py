from rest_framework.permissions import BasePermission, SAFE_METHODS

class CanRetrieveUpdateDeleteRoom(BasePermission):
    """
    - Allow GET to homeowners, family members, technicians.
    - Allow PATCH/DELETE only to technicians.
    """

    def has_permission(self, request, view):
        # Allow safe methods to all authenticated users
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # PATCH/DELETE allowed only for technicians
        return request.user.groups.filter(name='technician').exists()