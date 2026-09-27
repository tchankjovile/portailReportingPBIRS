import datetime
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from app.config import settings


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extrait la session utilisateur depuis le cookie JWT.
    Retourne None si aucune session valide (pas de fallback SSO).
    La vérification d'authentification est à la charge des routes.
    """
    token = request.cookies.get(settings.COOKIE_NAME)
    if token:
        user_data = decode_token(token)
        if user_data:
            return user_data
    return None


def require_authenticated_user(request: Request) -> Dict[str, Any]:
    """
    Dépendance FastAPI : exige une session authentifiée valide.
    Lève HTTP 401 si pas de cookie / token expiré.
    Les routes protégées utilisent cette fonction.
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié. Veuillez vous connecter.",
            headers={"X-Redirect-To": "/login"}
        )
    return user


def is_admin(user: Optional[Dict[str, Any]]) -> bool:
    """
    Retourne True si l'utilisateur appartient au groupe PBIRS-ADMINS.
    Utilisé dans les templates Jinja2 et les gardes de routes.
    """
    if not user:
        return False
    groups = user.get("groups", [])
    return "PBIRS-ADMINS" in groups


def require_admin(request: Request) -> Dict[str, Any]:
    """
    Dépendance FastAPI : exige l'appartenance au groupe PBIRS-ADMINS.
    Lève HTTP 403 si l'utilisateur n'est pas administrateur.
    """
    user = require_authenticated_user(request)
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs PBIRS (groupe PBIRS-ADMINS)."
        )
    return user
