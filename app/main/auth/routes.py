"""
Authentication routes - FastAPI version.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.schemas.auth_schema import RegisterSchema, LoginSchema
from app.main.auth.auth0_utils import get_auth_claims, get_auth0_user_id, verify_jwt
from app.main.auth.service import AuthService
from app.exceptions import UnauthorizedException
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Auth"])


@router.post("/callback")
def auth0_callback(body: dict):
    """
    Handle Auth0 callback after successful authentication.
    Frontend sends JWT token here after Auth0 redirect.

    Request Body:
    {
        "token": "eyJhbGc..."  // JWT access token from Auth0
    }
    """
    token = body.get("token")

    if not token:
        logger.warning("Auth0 callback called without token")
        raise UnauthorizedException("Token is required")

    # Verify JWT token
    claims = verify_jwt(token)
    logger.info(f"JWT verified for Auth0 user: {claims.get('sub')}")

    # Sync to database
    user = AuthService.process_auth0_login(claims)

    return {
        "user": user.to_dict(),
        "message": "Authentication successful",
        "token": token
    }


@router.get("/me")
def get_current_user(claims: dict = Depends(get_auth_claims)):
    """Get current authenticated user's profile."""
    auth0_user_id = claims.get("sub")
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    logger.debug(f"Fetched profile for user: {user.email}")
    return {"user": user.to_dict()}


@router.post("/refresh")
def refresh_session(claims: dict = Depends(get_auth_claims)):
    """Refresh user session and update last login timestamp."""
    auth0_user_id = claims.get("sub")
    user = AuthService.get_user_by_auth0_id(auth0_user_id)

    from app.main.auth.repository import AuthRepository
    AuthRepository.update_last_login(user.id)

    logger.info(f"Session refreshed for user: {user.email}")
    return {"user": user.to_dict(), "message": "Session refreshed"}


@router.post("/register")
def register(body: RegisterSchema):
    """Register new user with password (legacy/fallback)."""
    user = AuthService.register(
        email=body.email,
        password=body.password,
        name=body.name
    )
    logger.info(f"Legacy registration successful: {user.email}")
    return JSONResponse(
        status_code=201,
        content={
            "user": user.to_dict(),
            "message": "Registration successful (legacy mode)"
        }
    )


@router.post("/login")
def login(body: LoginSchema):
    """Login with email and password (legacy/fallback)."""
    user = AuthService.login(
        email=body.email,
        password=body.password
    )
    logger.info(f"Legacy login successful: {user.email}")
    return {"user": user.to_dict(), "message": "Login successful (legacy mode)"}
