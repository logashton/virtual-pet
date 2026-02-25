from __future__ import annotations

from rest_framework.authtoken.models import Token


def auth_token(request):
    if request.user.is_authenticated:
        token, _ = Token.objects.get_or_create(user=request.user)
        return {"auth_token": token.key}
    return {"auth_token": ""}
