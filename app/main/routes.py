"""
Main application routes (health check).
"""
from fastapi import APIRouter
from datetime import datetime
from app.utils.redis.client import redis_client

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    """
    Health check endpoint with Redis connectivity check.

    Returns:
        dict: Service health status
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {
            'redis': 'unknown'
        }
    }

    # Check Redis connectivity
    try:
        if redis_client.is_connected():
            health_status['checks']['redis'] = 'connected'
        else:
            health_status['checks']['redis'] = 'disconnected'
    except Exception as e:
        health_status['checks']['redis'] = f'error: {str(e)}'

    return health_status
