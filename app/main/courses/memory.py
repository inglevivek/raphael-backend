"""
Course memory management for hierarchical state storage.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone
import json

@dataclass
class TopicMemory:
    """Memory object for a single topic."""
    topic_id: str
    topic_number: int
    title: str
    key_points: List[str] = field(default_factory=list)
    explanation: Optional[str] = None
    videos: List[Dict] = field(default_factory=list)
    articles: List[Dict] = field(default_factory=list)
    token_count: int = 0
    status: str = 'pending'  # pending|generating|complete|failed
    generated_at: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'topicId': self.topic_id,
            'title': self.title,
            'keyPoints': self.key_points,
            'explanation': {
                'text': self.explanation or '',
                'sections': self._parse_sections() if self.explanation else []
            },
            'resources': {
                'videos': self.videos,
                'articles': self.articles
            },
            'metadata': {
                'tokenCount': self.token_count,
                'generatedAt': self.generated_at,
                'status': self.status
            }
        }
    
    def _parse_sections(self) -> List[Dict]:
        """Parse explanation text into sections if it contains headers."""
        # Simple markdown header parsing
        sections = []
        current_section = None
        
        for line in self.explanation.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'heading': line.replace('## ', '').strip(),
                    'content': ''
                }
            elif current_section:
                current_section['content'] += line + '\n'
        
        if current_section:
            sections.append(current_section)
        
        return sections if sections else []

@dataclass
class ChapterMemory:
    """Memory object for a chapter."""
    chapter_id: str
    chapter_number: int
    title: str
    topics: Dict[str, TopicMemory] = field(default_factory=dict)
    
    def add_topic(self, topic: TopicMemory):
        self.topics[topic.topic_id] = topic
    
    def to_index(self) -> Dict:
        return {
            'chapterId': self.chapter_id,
            'chapterNumber': self.chapter_number,
            'title': self.title,
            'estimatedMinutes': self._calculate_duration(),
            'topics': [
                {
                    'topicId': t.topic_id,
                    'topicNumber': t.topic_number,
                    'title': t.title,
                    'contentPath': t.topic_id
                }
                for t in sorted(self.topics.values(), key=lambda x: x.topic_number)
            ]
        }
    
    def _calculate_duration(self) -> int:
        """Estimate chapter duration based on content."""
        total_tokens = sum(t.token_count for t in self.topics.values())
        # Rough estimate: 200 tokens = 1 minute
        return max(5, total_tokens // 200)

@dataclass
class ModuleMemory:
    """Memory object for a module."""
    module_id: str
    module_number: int
    title: str
    description: Optional[str] = None
    chapters: Dict[str, ChapterMemory] = field(default_factory=dict)
    
    def add_chapter(self, chapter: ChapterMemory):
        self.chapters[chapter.chapter_id] = chapter
    
    def to_index(self) -> Dict:
        return {
            'moduleId': self.module_id,
            'moduleNumber': self.module_number,
            'title': self.title,
            'description': self.description,
            'chapters': [
                ch.to_index()
                for ch in sorted(self.chapters.values(), key=lambda x: x.chapter_number)
            ]
        }

class CourseMemory:
    """Parent memory object for entire course."""
    
    def __init__(self, course_id: int, topic: str, level: str):
        self.course_id = course_id
        self.topic = topic
        self.level = level
        self.modules: Dict[str, ModuleMemory] = {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        
    def add_module(self, module: ModuleMemory):
        self.modules[module.module_id] = module
    
    def get_all_topics(self) -> List[TopicMemory]:
        """Flatten all topics for batch processing."""
        topics = []
        for module in self.modules.values():
            for chapter in module.chapters.values():
                topics.extend(chapter.topics.values())
        return topics
    
    def get_topics_by_status(self, status: str) -> List[TopicMemory]:
        """Get topics filtered by status."""
        return [t for t in self.get_all_topics() if t.status == status]
    
    def export_course_file(self) -> Dict:
        """Export complete course structure for frontend."""
        all_topics = self.get_all_topics()
        
        return {
            'metadata': {
                'courseId': self.course_id,
                'topic': self.topic,
                'level': self.level,
                'createdAt': self.created_at,
                'version': '1.0'
            },
            'index': {
                'modules': [
                    mod.to_index()
                    for mod in sorted(self.modules.values(), key=lambda x: x.module_number)
                ]
            },
            'content': {
                topic.topic_id: topic.to_dict()
                for topic in all_topics
            }
        }
