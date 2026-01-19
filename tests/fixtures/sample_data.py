"""
Sample data fixtures for testing.
"""

SAMPLE_COURSE_FILE_EXPORT = {
    "metadata": {
        "courseId": 1,
        "topic": "Python Programming",
        "level": "beginner",
        "createdAt": "2026-01-19T12:00:00",
        "version": "1.0"
    },
    "index": {
        "modules": [
            {
                "moduleId": "mod_1",
                "moduleNumber": 1,
                "title": "Introduction to Python",
                "description": "Learn Python basics",
                "chapters": [
                    {
                        "chapterId": "mod_1_ch_1",
                        "chapterNumber": 1,
                        "title": "Getting Started",
                        "estimatedMinutes": 15,
                        "topics": [
                            {
                                "topicId": "mod_1_ch_1_top_1",
                                "topicNumber": 1,
                                "title": "Installing Python",
                                "contentPath": "mod_1_ch_1_top_1"
                            }
                        ]
                    }
                ]
            }
        ]
    },
    "content": {
        "mod_1_ch_1_top_1": {
            "topicId": "mod_1_ch_1_top_1",
            "title": "Installing Python",
            "keyPoints": [
                "Download from python.org",
                "Run installer",
                "Verify installation"
            ],
            "explanation": {
                "text": "Python installation is straightforward...",
                "sections": []
            },
            "resources": {
                "videos": [],
                "articles": []
            },
            "metadata": {
                "tokenCount": 0,
                "generatedAt": None,
                "status": "complete"
            }
        }
    }
}
