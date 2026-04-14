from fastapi import Request
from fastapi.responses import JSONResponse
from app.exceptions.not_found import NotFoundException
from app.exceptions.auth import (
    UnauthorizedException, InvalidCredentialsException,
    InvalidTokenException, EmailAlreadyExistsException,
    Auth0TokenException, Auth0JWKSException, Auth0SyncException,
    ForbiddenException
)
from app.exceptions.api_error import APIErrorException
from app.exceptions.validation import ValidationException
from app.exceptions.storage import StorageException


def register_exception_handlers(app):

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        return JSONResponse(status_code=404, content=exc.to_dict())

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request: Request, exc: UnauthorizedException):
        return JSONResponse(status_code=401, content=exc.to_dict())

    @app.exception_handler(InvalidCredentialsException)
    async def invalid_creds_handler(request: Request, exc: InvalidCredentialsException):
        return JSONResponse(status_code=401, content=exc.to_dict())

    @app.exception_handler(InvalidTokenException)
    async def invalid_token_handler(request: Request, exc: InvalidTokenException):
        return JSONResponse(status_code=401, content=exc.to_dict())

    @app.exception_handler(EmailAlreadyExistsException)
    async def email_exists_handler(request: Request, exc: EmailAlreadyExistsException):
        return JSONResponse(status_code=409, content=exc.to_dict())

    @app.exception_handler(Auth0TokenException)
    async def auth0_token_handler(request: Request, exc: Auth0TokenException):
        return JSONResponse(status_code=401, content=exc.to_dict())

    @app.exception_handler(Auth0JWKSException)
    async def auth0_jwks_handler(request: Request, exc: Auth0JWKSException):
        return JSONResponse(status_code=503, content=exc.to_dict())

    @app.exception_handler(Auth0SyncException)
    async def auth0_sync_handler(request: Request, exc: Auth0SyncException):
        return JSONResponse(status_code=500, content=exc.to_dict())

    @app.exception_handler(ForbiddenException)
    async def forbidden_handler(request: Request, exc: ForbiddenException):
        return JSONResponse(status_code=403, content=exc.to_dict())

    @app.exception_handler(APIErrorException)
    async def api_error_handler(request: Request, exc: APIErrorException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(ValidationException)
    async def validation_handler(request: Request, exc: ValidationException):
        return JSONResponse(status_code=422, content=exc.to_dict())

    @app.exception_handler(StorageException)
    async def storage_handler(request: Request, exc: StorageException):
        return JSONResponse(status_code=500, content=exc.to_dict())