"""
Main application routes (health check, etc.).
"""
from flask import Blueprint, jsonify
from datetime import datetime


main_bp = Blueprint('main', __name__)


@main_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint.
    
    Returns:
        tuple: (response, status_code)
        - 200: Service is healthy
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }), 200
