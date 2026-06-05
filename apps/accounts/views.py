"""Account endpoints — /api/me/, /api/login/, /api/logout/."""
from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import MeSerializer


class MeView(APIView):
    """GET /api/me/ — current user + org memberships.

    The frontend's first authenticated request. Without it, the user has no
    way to discover which orgs they can act on.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


class _LoginInput(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LoginView(APIView):
    """POST /api/login/  → session cookie + the same payload /api/me/ returns.

    No authentication required (it's the bootstrap) and no CSRF either —
    the password is the auth factor. After login, normal endpoints
    enforce CSRF via the standard SessionAuthentication path.

    Returns 200 + Me on success, 400 on bad-shape input, 401 on bad
    credentials. We deliberately return 401 (not 403) so the frontend
    can distinguish "wrong password" from "session expired".
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # skip SessionAuthentication's CSRF enforcement

    def post(self, request: Request) -> Response:
        ser = _LoginInput(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=ser.validated_data["email"],
            password=ser.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {"detail": "This account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, user)
        return Response(MeSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /api/logout/  → revoke the current session.

    Returns 204 unconditionally — anonymous callers don't error, they
    just succeed at no-op. Matches the principle that "log me out"
    should be hard to fail.
    """
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
