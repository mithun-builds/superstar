"""Account endpoints — currently just /api/me/."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
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
