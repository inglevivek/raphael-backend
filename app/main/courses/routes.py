"""
Course management routes.
"""
from flask import Blueprint, jsonify, request
from app.main.courses.service import CoursesService
from app.schemas import CreateCourseSchema
from app.utils.decorators import handle_errors, validate_schema
from app.utils.logger import get_logger
from uuid import UUID


logger = get_logger(__name__)

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('', methods=['POST'])
@handle_errors
@validate_schema(CreateCourseSchema)
def create_course():
    """
    Create new course and start generation.

    Request Body:
        {
            "user_id": "uuid-string",  # User ID
            "title": "Python Programming",
            "level": "beginner"
        }

    Returns:
        tuple: (response, status_code)
        - 201: Course creation started
        - 400: Validation error
    """
    data = request.validated_data
    user_id = data.get('user_id') or request.args.get('user_id')
    
    if not user_id:
        raise ValueError('user_id is required')

    course = CoursesService.create_course(
        user_id=user_id,
        title=data['title'],
        level=data['level']
    )

    return jsonify(course), 201


@courses_bp.route('', methods=['GET'])
@handle_errors
def list_courses():
    """
    List all user's courses.

    Query Parameters:
        user_id: User UUID

    Returns:
        tuple: (response, status_code)
        - 200: List of courses
    """
    user_id = request.args.get('user_id')
    if not user_id:
        raise ValueError('user_id is required')
    
    courses = CoursesService.get_user_courses(user_id)
    return jsonify(courses), 200


@courses_bp.route('/<string:course_id>', methods=['GET'])
@handle_errors
def get_course(course_id: UUID):
    """
    Get course details for status polling.

    Path Parameters:
        course_id (str): Course UUID

    Query Parameters:
        user_id: User UUID

    Returns:
        tuple: (response, status_code)
        - 200: Course details
        - 404: Course not found
    """
    user_id = request.args.get('user_id')
    if not user_id:
        raise ValueError('user_id is required')
    
    course = CoursesService.get_course_details(user_id, course_id)
    return jsonify(course), 200


@courses_bp.route('/<string:course_id>/content', methods=['GET'])
@handle_errors
def get_course_content(course_id: UUID):
    """
    Get course with full content.

    Path Parameters:
        course_id (str): Course UUID

    Query Parameters:
        user_id: User UUID

    Returns:
        tuple: (response, status_code)
        - 200: Course with full content
        - 400: Course not ready
        - 404: Course not found
    """
    user_id = request.args.get('user_id')
    if not user_id:
        raise ValueError('user_id is required')
    
    course = CoursesService.get_course_content(user_id, course_id)
    return jsonify(course), 200


@courses_bp.route('/<string:course_id>', methods=['DELETE'])
@handle_errors
def delete_course(course_id: UUID):
    """
    Delete course.

    Path Parameters:
        course_id (str): Course UUID

    Query Parameters:
        user_id: User UUID

    Returns:
        tuple: (response, status_code)
        - 200: Course deleted
        - 404: Course not found
    """
    user_id = request.args.get('user_id')
    if not user_id:
        raise ValueError('user_id is required')
    
    CoursesService.delete_course(user_id, course_id)
    return jsonify({'message': 'Course deleted successfully'}), 200
