# youtube_scraper.py (~200-250 lines total)

import asyncio
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass
import time
import logging
import re

# Lightweight extraction
try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, ExtractorError
except ImportError:
    raise ImportError("Install yt-dlp: pip install yt-dlp")

logger = logging.getLogger(__name__)

class YouTubeClient:
    """Drop-in replacement for YouTube Data API using web scraping."""
    
    def __init__(self, api_key: str = None):
        # api_key ignored but accepted for compatibility
        self._lock = threading.Lock()
        self._session = None
        self._semaphore = asyncio.Semaphore(5)  # Concurrent limit
        self._last_request = 0
        self._min_delay = 0.5  # Rate limiting
        
        # yt-dlp config (lightweight, no download)
        self._ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just metadata
            'skip_download': True,
            'format': 'worst',  # Minimal bandwidth
        }
        logger.info("YouTube scraper initialized")
    
    def search_videos(self, query: str, max_results: int = 3, 
                     max_retries: int = 3) -> List[Dict]:
        """Sync wrapper for async search (maintains compatibility)."""
        thread_id = threading.current_thread().name
        
        # Run async search in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self._search_async(query, max_results, max_retries, thread_id)
        )
    
    async def _search_async(self, query: str, max_results: int, 
                           max_retries: int, thread_id: str) -> List[Dict]:
        """Core async search implementation."""
        for attempt in range(max_retries):
            try:
                logger.info(f"[{thread_id}] Searching YouTube: {query}")
                
                # Rate limiting
                await self._enforce_rate_limit()
                
                # Use yt-dlp's search extractor
                search_url = f"ytsearch{max_results}:{query}"
                
                async with self._semaphore:
                    with YoutubeDL(self._ydl_opts) as ydl:
                        result = ydl.extract_info(search_url, download=False)
                
                videos = []
                for item in result.get('entries', [])[:max_results]:
                    if not item:
                        continue
                    
                    video = {
                        'id': item.get('id', ''),
                        'title': item.get('title', ''),
                        'channel': item.get('uploader', item.get('channel', '')),
                        'thumbnail': self._get_best_thumbnail(item),
                        'embed_url': f"https://www.youtube.com/embed/{item.get('id', '')}"
                    }
                    videos.append(video)
                
                logger.info(f"[{thread_id}] Found {len(videos)} videos")
                return videos
                
            except (DownloadError, ExtractorError) as e:
                logger.warning(f"[{thread_id}] Extraction error: {str(e)}")
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    logger.info(f"[{thread_id}] Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"[{thread_id}] Failed after {max_retries} attempts")
                    return []
            
            except Exception as e:
                logger.error(f"[{thread_id}] Unexpected error: {type(e).__name__}: {str(e)}")
                return []
        
        return []
    
    async def _enforce_rate_limit(self):
        """Prevent overwhelming YouTube."""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request = time.time()
    
    def _get_best_thumbnail(self, item: dict) -> str:
        """Extract highest quality thumbnail."""
        thumbnails = item.get('thumbnails', [])
        if not thumbnails:
            return ''
        
        # Prefer 'high' quality or largest resolution
        for thumb in reversed(thumbnails):
            if thumb.get('url'):
                return thumb['url']
        return ''
    
    # Batch methods for concurrency (future enhancement)
    async def search_videos_batch(self, queries: List[str], 
                                  max_results: int = 3) -> List[List[Dict]]:
        """Concurrent batch search."""
        tasks = [
            self._search_async(q, max_results, 3, f"batch_{i}")
            for i, q in enumerate(queries)
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
