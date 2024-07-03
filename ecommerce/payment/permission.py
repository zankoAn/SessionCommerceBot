from rest_framework.permissions import BasePermission


class WhitelistIPPermission(BasePermission):
    allowed_ips = ["127.0.0.1", "91.227.144.54"]

    def has_permission(self, request, view):
        ips = request.META.get("HTTP_X_FORWARDED_FOR").split(",")[0]
        return ips in self.allowed_ips
