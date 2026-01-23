"""
Custom decorators for request handling and validation.
"""
from functools import wraps
from flask import request, jsonify
from pydantic import BaseModel, ValidationError
from typing import Type, Callable
from app.exceptions import BaseAPIException, ValidationException
from app.utils.logger import get_logger

logger = get_logger(__name__)


def handle_errors(f: Callable) -> Callable:
    """
    Decorator to catch and handle exceptions in route handlers.
    Converts custom exceptions to JSON responses.

    Usage:
        @handle_errors
        def my_route():
            ...

    Args:
        f (Callable): Route handler function

    Returns:
        Callable: Wrapped function with error handling
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BaseAPIException as e:
            logger.warning(f"API Exception: {e.message}", exc_info=True)
            return jsonify(e.to_dict()), e.status_code
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            return jsonify({
                'error': str(e),
                'status_code': 400
            }), 400
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'status_code': 500
            }), 500

    return decorated_function


def validate_schema(schema_class: Type[BaseModel]) -> Callable:
    """
    Decorator to validate request body against Pydantic schema.

    Usage:
        @validate_schema(RegisterSchema)
        def register():
            data = request.validated_data
            ...

    Args:
        schema_class (Type[BaseModel]): Pydantic model class for validation

    Returns:
        Callable: Decorator function

    Raises:
        ValidationException: If request body validation fails
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get JSON data from request
                data = request.get_json()
                if data is None:
                    raise ValidationException("Request body must be JSON")

                # Validate against schema
                validated = schema_class(**data)

                # Attach validated data to request
                request.validated_data = validated.model_dump()

                return f(*args, **kwargs)

            except ValidationError as e:
                logger.warning(f"Validation error: {e}")
                errors = []
                for error in e.errors():
                    field = '.'.join(str(x) for x in error['loc'])
                    message = error['msg']
                    errors.append(f"{field}: {message}")
                raise ValidationException("; ".join(errors))

        return decorated_function
    return decorator
