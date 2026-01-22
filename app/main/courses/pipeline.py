"""
Course generation pipeline with UUID support, Rich logging, and integrated checkpoint management.
"""
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from flask import current_app
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from app.main.courses.repository import CoursesRepository
from app.main.courses.checkpoint_manager import CheckpointManager
from app.main.courses.memory import (
    CourseMemory, ModuleMemory, ChapterMemory, TopicMemory
)
from app.utils.youtube import YouTubeClient
from app.utils.groq import GroqClient

# Rich console for beautiful output
console = Console()


class CourseGeneratorPipeline:
    """Memory-based pipeline with checkpoint management and Rich logging."""

    # Configuration
    MAX_RETRIES = 3
    BACKOFF_BASE = 5.0
    MIN_REQUEST_DELAY = 4.0
    YOUTUBE_MAX_RESULTS = 3

    def __init__(self, course_id: str):
        """
        Initialize pipeline for a course.

        Args:
            course_id (str): Course UUID string
        """
        # Convert to UUID if needed
        self.course_id = str(UUID(course_id)) if isinstance(course_id, str) else str(course_id)

        self.course = None
        self.memory: CourseMemory = None
        self.checkpoint_manager: CheckpointManager = None

        # API clients (initialized in generate())
        self.groq_client = None
        self.youtube_client = None

        # Prompts directory
        self.prompts_dir = Path(__file__).parent / 'prompts'

        # Rate limiting
        self.last_request_time = None
        self.request_count = 0
        self.retry_count = 0

    # ==================== MAIN GENERATION METHOD ====================

    def generate(self) -> None:
        """Execute complete 5-stage pipeline with checkpoint support."""
        try:
            # Initialize
            self._initialize()

            # Display header
            self._display_header()

            # Try to resume from checkpoint
            resumed_stage = self._try_resume()

            # Determine stages to run
            stages_to_run = self._determine_stages(resumed_stage)

            # Execute stages
            for stage_num, stage_name in enumerate(stages_to_run, 1):
                with console.status(f"[bold cyan]Stage {stage_num}: {stage_name}...", spinner="dots"):
                    if stage_name == 'Generate Outline':
                        self._stage1_generate_outline()
                    elif stage_name == 'Expand Points':
                        self._stage2_expand_points()
                    elif stage_name == 'Generate Content':
                        self._stage3_generate_content()
                    elif stage_name == 'Aggregate Resources':
                        self._stage4_aggregate_resources()
                    elif stage_name == 'Export Course':
                        self._stage5_export()

            # Display completion
            self._display_completion()

        except Exception as e:
            console.print(f"[bold red]✗ Pipeline failed: {str(e)}")

            # Save crash checkpoint
            try:
                if self.memory and self.checkpoint_manager:
                    self.checkpoint_manager.log_error('crash', str(e))
            except:
                pass

            CoursesRepository.mark_failed(self.course_id, str(e))
            raise

    # ==================== INITIALIZATION ====================

    def _initialize(self):
        """Initialize course, clients, and checkpoint manager."""
        self.course = CoursesRepository.get_by_id(self.course_id)

        # Initialize API clients
        self.groq_client = GroqClient(current_app.config['GROQ_API_KEY'])
        self.youtube_client = YouTubeClient(current_app.config['YOUTUBE_API_KEY'])

        # Initialize checkpoint manager
        self.checkpoint_manager = CheckpointManager(self.course_id)

    def _display_header(self):
        """Display pipeline header."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="cyan bold")
        table.add_column()

        table.add_row("Course ID:", str(self.course_id)[:13] + "...")
        table.add_row("Title:", self.course.title)
        table.add_row("Level:", self.course.level.upper())

        console.print(Panel(table, title="[bold cyan]🚀 Course Generation Pipeline", border_style="cyan"))

    def _try_resume(self) -> Optional[str]:
        """Try to resume from checkpoint."""
        stages = ['stage4', 'stage3', 'stage2', 'stage1']

        for stage in stages:
            data = self.checkpoint_manager.get_stage_data(stage)
            if data:
                # Deserialize memory
                self.memory = self._deserialize_memory(data)
                total_topics = len(self.memory.get_all_topics())

                console.print(f"[yellow]🔄 Resuming from {stage} with {total_topics} topics")
                return stage

        return None

    def _determine_stages(self, resumed_stage: Optional[str]) -> List[str]:
        """Determine which stages to run based on resume point."""
        all_stages = [
            'Generate Outline',
            'Expand Points', 
            'Generate Content',
            'Aggregate Resources',
            'Export Course'
        ]

        if resumed_stage is None:
            return all_stages
        elif resumed_stage == 'stage1':
            return all_stages[1:]
        elif resumed_stage == 'stage2':
            return all_stages[2:]
        elif resumed_stage == 'stage3':
            return all_stages[3:]
        elif resumed_stage == 'stage4':
            return all_stages[4:]
        else:
            return []

    # ==================== STAGE 1: GENERATE OUTLINE ====================

    def _stage1_generate_outline(self):
        """Stage 1: Generate course outline and populate memory."""
        console.print("\n[bold cyan]📋 Stage 1: Generating Outline")

        # Load prompt
        prompt_template = self._load_prompt('outline_prompt.txt')
        prompt = prompt_template.format(
            title=self.course.title,
            level=self.course.level
        )

        # Call LLM
        self._enforce_rate_limit()
        outline = self.groq_client.generate_json(prompt, validate_outline=True)

        # Save LLM context
        self.checkpoint_manager.save_llm_context('stage1', prompt, outline)

        # Initialize memory
        self.memory = CourseMemory(self.course_id, self.course.title, self.course.level)

        # Populate memory hierarchy
        self._populate_memory_from_outline(outline)

        # Save checkpoint
        memory_data = self._serialize_memory()
        self.checkpoint_manager.save_stage_data('stage1', memory_data)
        self.checkpoint_manager.mark_stage_complete('stage1')

        total_topics = len(self.memory.get_all_topics())
        console.print(f"[green]✓ Outline created: {len(self.memory.modules)} modules, {total_topics} topics")

    def _populate_memory_from_outline(self, outline: dict):
        """Populate memory structure from LLM outline."""
        # Handle old format adaptation
        if 'modules' not in outline and 'chapter_number' in outline:
            outline = {
                'modules': [{
                    'module_number': 1,
                    'module_title': f'Introduction to {self.course.title}',
                    'description': f'Core {self.course.title} concepts',
                    'chapters': [outline]
                }]
            }

        # Populate hierarchy
        for mod_idx, module_data in enumerate(outline.get('modules', []), 1):
            module_id = f"mod_{mod_idx}"
            module = ModuleMemory(
                module_id=module_id,
                module_number=mod_idx,
                title=module_data.get('module_title', ''),
                description=module_data.get('description')
            )

            for ch_idx, chapter_data in enumerate(module_data.get('chapters', []), 1):
                chapter_id = f"{module_id}_ch_{ch_idx}"
                chapter = ChapterMemory(
                    chapter_id=chapter_id,
                    chapter_number=ch_idx,
                    title=chapter_data.get('chapter_title', '')
                )

                for top_idx, topic_data in enumerate(chapter_data.get('topics', []), 1):
                    topic_id = f"{chapter_id}_top_{top_idx}"
                    topic = TopicMemory(
                        topic_id=topic_id,
                        topic_number=top_idx,
                        title=topic_data.get('topic_title', '')
                    )
                    chapter.add_topic(topic)

                module.add_chapter(chapter)

            self.memory.add_module(module)

    # ==================== STAGE 2: EXPAND POINTS ====================

    def _stage2_expand_points(self):
        """Stage 2: Expand key points for all topics."""
        console.print("\n[bold cyan]🔍 Stage 2: Expanding Key Points")

        topics = [t for t in self.memory.get_all_topics() if t.status == 'pending']
        prompt_template = self._load_prompt('expand_points_prompt.txt')

        completed = 0
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Expanding points...", total=len(topics))

            for topic in topics:
                result = self._expand_topic_points(topic, prompt_template)

                if result.status == 'points_complete':
                    completed += 1
                else:
                    failed += 1

                # Update last successful topic
                if result.status == 'points_complete':
                    self.checkpoint_manager.update_last_successful_topic(topic.topic_id)

                progress.update(task, advance=1)

        # Save checkpoint
        memory_data = self._serialize_memory()
        self.checkpoint_manager.save_stage_data('stage2', memory_data)
        self.checkpoint_manager.mark_stage_complete('stage2')

        console.print(f"[green]✓ Points expanded: {completed} succeeded, {failed} failed")

    def _expand_topic_points(self, topic: TopicMemory, prompt_template: str) -> TopicMemory:
        """Expand key points for a single topic with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                self._enforce_rate_limit()

                # Find parent context
                module, chapter = self._find_topic_parents(topic.topic_id)

                # Build prompt
                prompt = prompt_template.format(
                    topic_title=topic.title,
                    module_title=module.title if module else '',
                    chapter_title=chapter.title if chapter else '',
                    level=self.course.level,
                    topic_number=topic.topic_number
                )

                # Call LLM
                result = self.groq_client.generate_json(prompt)

                # Update topic
                topic.key_points = result.get('points', [])
                topic.status = 'points_complete'

                return topic

            except Exception as e:
                self.retry_count += 1

                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._calculate_backoff(attempt)
                    time.sleep(backoff)
                else:
                    topic.status = 'failed'
                    topic.error = str(e)
                    self.checkpoint_manager.log_error('stage2', f"{topic.topic_id}: {str(e)}")
                    return topic

        return topic

    # ==================== STAGE 3: GENERATE CONTENT ====================

    def _stage3_generate_content(self):
        """Stage 3: Generate detailed explanations."""
        console.print("\n[bold cyan]✍️  Stage 3: Generating Content")

        topics = self.memory.get_topics_by_status('points_complete')
        prompt_template = self._load_prompt('explanation_prompt.txt')

        completed = 0
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Generating content...", total=len(topics))

            for topic in topics:
                result = self._generate_topic_content(topic, prompt_template)

                if result.status == 'content_complete':
                    completed += 1
                else:
                    failed += 1

                # Update last successful topic
                if result.status == 'content_complete':
                    self.checkpoint_manager.update_last_successful_topic(topic.topic_id)

                progress.update(task, advance=1)

        # Save checkpoint
        memory_data = self._serialize_memory()
        self.checkpoint_manager.save_stage_data('stage3', memory_data)
        self.checkpoint_manager.mark_stage_complete('stage3')

        console.print(f"[green]✓ Content generated: {completed} succeeded, {failed} failed")

    def _generate_topic_content(self, topic: TopicMemory, prompt_template: str) -> TopicMemory:
        """Generate content for a single topic with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                self._enforce_rate_limit()

                # Build prompt
                points_text = '\n'.join(f"- {point}" for point in topic.key_points)
                prompt = prompt_template.format(
                    topic_title=topic.title,
                    level=self.course.level,
                    points=points_text
                )

                # Call LLM
                explanation = self.groq_client.generate(prompt)

                # Update topic
                topic.explanation = explanation
                topic.token_count = len(explanation.split())
                topic.status = 'content_complete'
                topic.generated_at = datetime.now(timezone.utc).isoformat()

                return topic

            except Exception as e:
                self.retry_count += 1

                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._calculate_backoff(attempt)
                    time.sleep(backoff)
                else:
                    topic.status = 'failed'
                    topic.error = str(e)
                    self.checkpoint_manager.log_error('stage3', f"{topic.topic_id}: {str(e)}")
                    return topic

        return topic

    # ==================== STAGE 4: AGGREGATE RESOURCES ====================

    def _stage4_aggregate_resources(self):
        """Stage 4: Fetch YouTube videos for topics."""
        console.print("\n[bold cyan]🎥 Stage 4: Aggregating Resources")

        topics = self.memory.get_topics_by_status('content_complete')

        completed = 0
        failed = 0
        quota_exhausted = False

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Fetching videos...", total=len(topics))

            for topic in topics:
                if quota_exhausted:
                    topic.videos = []
                    topic.status = 'complete'
                    failed += 1
                    progress.update(task, advance=1)
                    continue

                try:
                    search_query = f"{self.course.title} {topic.title} tutorial"
                    videos = self.youtube_client.search_videos(
                        search_query, 
                        max_results=self.YOUTUBE_MAX_RESULTS
                    )

                    topic.videos = videos
                    topic.status = 'complete'

                    if videos:
                        completed += 1
                    else:
                        failed += 1

                    # Rate limiting
                    time.sleep(0.5)

                except Exception as e:
                    if 'quotaExceeded' in str(e) or 'quota' in str(e).lower():
                        quota_exhausted = True
                        console.print("[yellow]⚠ YouTube API quota exhausted")

                    topic.videos = []
                    topic.status = 'complete'
                    failed += 1
                    self.checkpoint_manager.log_error('stage4', f"{topic.topic_id}: {str(e)}")

                progress.update(task, advance=1)

        # Save checkpoint
        memory_data = self._serialize_memory()
        self.checkpoint_manager.save_stage_data('stage4', memory_data)
        self.checkpoint_manager.mark_stage_complete('stage4')

        console.print(f"[green]✓ Resources aggregated: {completed} succeeded, {failed} failed")

    # ==================== STAGE 5: EXPORT ====================

    def _stage5_export(self):
        """Stage 5: Export course to database."""
        console.print("\n[bold cyan]💾 Stage 5: Exporting Course")

        # Export course structure
        course_json = self.memory.export_course_file()

        # Calculate statistics
        all_topics = self.memory.get_all_topics()
        total_modules = len(self.memory.modules)
        total_chapters = sum(len(mod.chapters) for mod in self.memory.modules.values())
        total_topics = len(all_topics)

        # Estimate duration (rough: 200 tokens = 1 minute)
        total_tokens = sum(t.token_count or 0 for t in all_topics)
        estimated_minutes = max(30, total_tokens // 200)

        # Update course in database
        CoursesRepository.update_course_json(
            self.course_id,
            course_json,
            total_modules=total_modules,
            total_chapters=total_chapters,
            total_topics=total_topics,
            estimated_minutes=estimated_minutes
        )

        # Mark completed
        CoursesRepository.mark_completed(self.course_id)

        console.print(f"[green]✓ Course exported to database")

    # ==================== COMPLETION ====================

    def _display_completion(self):
        """Display completion statistics."""
        all_topics = self.memory.get_all_topics()
        complete = sum(1 for t in all_topics if t.status == 'complete')
        failed = sum(1 for t in all_topics if t.status == 'failed')

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column(style="green")

        table.add_row("Total Topics:", str(len(all_topics)))
        table.add_row("Completed:", f"{complete} ({complete/len(all_topics)*100:.1f}%)")
        table.add_row("Failed:", f"{failed} ({failed/len(all_topics)*100:.1f}%)")
        table.add_row("API Requests:", str(self.request_count))
        table.add_row("Retries:", str(self.retry_count))

        console.print("\n")
        console.print(Panel(
            table, 
            title="[bold green]✓ Course Generation Complete",
            border_style="green"
        ))

    # ==================== UTILITY METHODS ====================

    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from file."""
        prompt_path = self.prompts_dir / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _enforce_rate_limit(self):
        """Enforce minimum delay between API requests."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.MIN_REQUEST_DELAY:
                time.sleep(self.MIN_REQUEST_DELAY - elapsed)

        self.last_request_time = time.time()
        self.request_count += 1

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        import random
        base_delay = self.BACKOFF_BASE * (2 ** attempt)
        jitter = random.uniform(0, 1)
        return min(base_delay + jitter, 60.0)

    def _find_topic_parents(self, topic_id: str) -> Tuple[Optional[ModuleMemory], Optional[ChapterMemory]]:
        """Find parent module and chapter for a topic."""
        for module in self.memory.modules.values():
            for chapter in module.chapters.values():
                if topic_id in chapter.topics:
                    return module, chapter
        return None, None

    # ==================== SERIALIZATION ====================

    def _serialize_memory(self) -> dict:
        """Convert CourseMemory to JSON-serializable dict."""
        return {
            'course_id': self.memory.course_id,
            'title': self.memory.title,
            'level': self.memory.level,
            'modules': {
                module_id: {
                    'module_id': module.module_id,
                    'module_number': module.module_number,
                    'title': module.title,
                    'description': module.description,
                    'chapters': {
                        chapter_id: {
                            'chapter_id': chapter.chapter_id,
                            'chapter_number': chapter.chapter_number,
                            'title': chapter.title,
                            'topics': {
                                topic_id: {
                                    'topic_id': topic.topic_id,
                                    'topic_number': topic.topic_number,
                                    'title': topic.title,
                                    'key_points': topic.key_points or [],
                                    'explanation': topic.explanation,
                                    'videos': topic.videos or [],
                                    'status': topic.status,
                                    'token_count': topic.token_count or 0,
                                    'generated_at': topic.generated_at,
                                    'error': topic.error
                                }
                                for topic_id, topic in chapter.topics.items()
                            }
                        }
                        for chapter_id, chapter in module.chapters.items()
                    }
                }
                for module_id, module in self.memory.modules.items()
            }
        }

    def _deserialize_memory(self, data: dict) -> CourseMemory:
        """Reconstruct CourseMemory from serialized dict."""
        memory = CourseMemory(data['course_id'], data['title'], data['level'])

        for module_data in data['modules'].values():
            module = ModuleMemory(
                module_id=module_data['module_id'],
                module_number=module_data['module_number'],
                title=module_data['title'],
                description=module_data.get('description')
            )

            for chapter_data in module_data['chapters'].values():
                chapter = ChapterMemory(
                    chapter_id=chapter_data['chapter_id'],
                    chapter_number=chapter_data['chapter_number'],
                    title=chapter_data['title']
                )

                for topic_data in chapter_data['topics'].values():
                    topic = TopicMemory(
                        topic_id=topic_data['topic_id'],
                        topic_number=topic_data['topic_number'],
                        title=topic_data['title']
                    )

                    topic.key_points = topic_data.get('key_points', [])
                    topic.explanation = topic_data.get('explanation')
                    topic.videos = topic_data.get('videos', [])
                    topic.status = topic_data.get('status', 'pending')
                    topic.token_count = topic_data.get('token_count', 0)
                    topic.generated_at = topic_data.get('generated_at')
                    topic.error = topic_data.get('error')

                    chapter.add_topic(topic)

                module.add_chapter(chapter)

            memory.add_module(module)

        return memory