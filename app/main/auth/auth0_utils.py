"""
Auth0 JWT verification and utilities.
Migrated to FastAPI: removed Flask g/request/current_app, replaced with
os.environ and FastAPI Depends-based dependency functions.
"""
from functools import lru_cache
from typing import Any, Dict, Optional
import os
import requests
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import proper exception classes
from app.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    Auth0TokenException,
    Auth0JWKSException
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer()


@lru_cache(maxsize=5)
def fetch_jwks(domain: str) -> Dict[str, Any]:
    """
    Fetch JSON Web Key Set (JWKS) from Auth0.
    Cached to avoid repeated network calls.

    Args:
        domain (str): Auth0 domain

    Returns:
        dict: JWKS containing public keys

    Raises:
        Auth0JWKSException: If JWKS fetch fails
    """
    url = f"https://{domain}/.well-known/jwks.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        logger.debug(f"Fetched JWKS from {url}")
        return response.json()
    except requests.RequestException as exc:
        logger.error(f"Failed to fetch JWKS: {exc}")
        raise Auth0JWKSException("Unable to fetch JWKS for token verification.") from exc


def build_rsa_key(keys: list, kid: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Build RSA key from JWKS for token verification.

    Args:
        keys (list): List of keys from JWKS
        kid (str): Key ID from JWT header

    Returns:
        dict: RSA key dictionary or None if not found
    """
    if not kid:
        return None

    for key in keys:
        if key.get("kid") == kid:
            return {
                "kty": key.get("kty"),
                "kid": key.get("kid"),
                "use": key.get("use"),
                "n": key.get("n"),
                "e": key.get("e"),
            }

    return None


def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verify Auth0 JWT token and return claims.

    Args:
        token (str): JWT token from Authorization header

    Returns:
        dict: Token claims (includes 'sub', 'email', 'permissions', etc.)

    Raises:
        Auth0TokenException: If token is invalid, expired, or verification fails
    """
    domain = os.getenv("AUTH0_DOMAIN")
    audience = os.getenv("AUTH0_AUDIENCE")
    algorithms = os.getenv("AUTH0_ALGORITHMS", "RS256").split(",")

    if not domain or not audience:
        logger.error("Auth0 configuration missing")
        raise Auth0TokenException("Auth0 configuration is missing.")

    # Get unverified header to extract kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        logger.warning(f"Invalid token header: {exc}")
        raise Auth0TokenException("Invalid token header.") from exc

    # Fetch JWKS and build RSA key
    jwks = fetch_jwks(domain)
    rsa_key = build_rsa_key(jwks.get("keys", []), unverified_header.get("kid"))

    # ← ADD: Retry once with fresh JWKS if key not found (handles key rotation)
    if not rsa_key:
        logger.warning("RSA key not found in cached JWKS, retrying with fresh fetch...")
        fetch_jwks.cache_clear()
        jwks = fetch_jwks(domain)
        rsa_key = build_rsa_key(jwks.get("keys", []), unverified_header.get("kid"))

    if not rsa_key:
        logger.warning("Unable to find appropriate RSA key")
        raise Auth0TokenException("Unable to find an appropriate key.")

    issuer = f"https://{domain}/"

    # Verify and decode token
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
        )
        logger.debug(f"Token verified successfully for sub: {payload.get('sub')}")
        return payload

    except ExpiredSignatureError as exc:
        logger.warning("Token expired")
        raise Auth0TokenException("Token is expired.") from exc

    except JWTError as exc:
        logger.warning(f"Token verification failed: {exc}")
        raise Auth0TokenException("Unable to parse authentication token.") from exc


def get_auth_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    FastAPI dependency. Use as: claims: dict = Depends(get_auth_claims)
    Returns the full JWT claims dict.
    Raises Auth0TokenException on invalid token (caught by exception handler).
    """
    token = credentials.credentials
    claims = verify_jwt(token)  # existing function, raises Auth0TokenException
    return claims


def get_auth0_user_id(claims: dict = Depends(get_auth_claims)) -> str:
    """Returns Auth0 user ID (sub claim)."""
    sub = claims.get("sub")
    if not sub:
        raise UnauthorizedException("Missing sub claim in token")
    return sub


def get_user_email(claims: dict = Depends(get_auth_claims)) -> str:
    """Returns user email from token claims."""
    return claims.get("email")


def get_user_permissions(claims: dict = Depends(get_auth_claims)) -> list:
    """Returns user permissions from token claims."""
    return claims.get("permissions", [])
