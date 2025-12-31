"""
Course management routes.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.main.courses.service import CoursesService
from app.schemas import CreateCourseSchema
from app.utils.decorators import handle_errors, validate_schema
from app.utils.logger import get_logger


logger = get_logger(__name__)
courses_bp = Blueprint('courses', __name__, url_prefix='/api/courses')


@courses_bp.route('', methods=['POST'])
@jwt_required()
@handle_errors
@validate_schema(CreateCourseSchema)
def create_course():
    """
    Create new course and start generation.
    
    Headers:
        Authorization: Bearer <token>
    
    Request Body:
        {
            "topic": "Python Programming",
            "level": "beginner"
        }
    
    Returns:
        tuple: (response, status_code)
        - 201: Course creation started
        - 400: Validation error
        - 401: Unauthorized
    """
    user_id = get_jwt_identity()
    data = request.validated_data
    
    course = CoursesService.create_course(
        user_id=user_id,
        topic=data['topic'],
        level=data['level']
    )
    
    return jsonify(course), 201


@courses_bp.route('', methods=['GET'])
@jwt_required()
@handle_errors
def list_courses():
    """
    List all user's courses.
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        tuple: (response, status_code)
        - 200: List of courses
        - 401: Unauthorized
    """
    user_id = get_jwt_identity()
    courses = CoursesService.get_user_courses(user_id)
    return jsonify(courses), 200


@courses_bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
@handle_errors
def get_course(course_id: int):
    """
    Get course details for status polling.
    
    Headers:
        Authorization: Bearer <token>
    
    Path Parameters:
        course_id (int): Course ID
    
    Returns:
        tuple: (response, status_code)
        - 200: Course details
        - 401: Unauthorized
        - 404: Course not found
    """
    user_id = get_jwt_identity()
    course = CoursesService.get_course_details(user_id, course_id)
    return jsonify(course), 200


@courses_bp.route('/<int:course_id>/content', methods=['GET'])
@jwt_required()
@handle_errors
def get_course_content(course_id: int):
    """
    Get course with full content.
    
    Headers:
        Authorization: Bearer <token>
    
    Path Parameters:
        course_id (int): Course ID
    
    Returns:
        tuple: (response, status_code)
        - 200: Course with full content
        - 400: Course not ready
        - 401: Unauthorized
        - 404: Course not found
    """
    user_id = get_jwt_identity()
    course = CoursesService.get_course_content(user_id, course_id)
    return jsonify(course), 200


@courses_bp.route('/<int:course_id>', methods=['DELETE'])
@jwt_required()
@handle_errors
def delete_course(course_id: int):
    """
    Delete course.
    
    Headers:
        Authorization: Bearer <token>
    
    Path Parameters:
        course_id (int): Course ID
    
    Returns:
        tuple: (response, status_code)
        - 200: Course deleted
        - 401: Unauthorized
        - 404: Course not found
    """
    user_id = get_jwt_identity()
    CoursesService.delete_course(user_id, course_id)
    return jsonify({'message': 'Course deleted successfully'}), 200
