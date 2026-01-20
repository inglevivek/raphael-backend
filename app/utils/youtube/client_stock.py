"""
YouTube API client for video search and retrieval.
"""
from typing import List, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from http.client import IncompleteRead  # For incomplete HTTP responses
from urllib3.exceptions import ProtocolError  # Alternative urllib3 exception
from app.utils.logger import get_logger

import time
import threading
from ssl import SSLError


logger = get_logger(__name__)


class YouTubeClient:
    """Client for interacting with YouTube Data API v3."""
    
    def __init__(self, api_key: str):
        """
        Initialize YouTube client with API key.
        
        Args:
            api_key (str): YouTube Data API key
        
        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("YouTube API key is required")
        self._api_key = api_key
        self._lock = threading.Lock()
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        logger.info("YouTube client initialized")
    
    def search_videos(self, query: str, max_results: int = 3, max_retries: int = 3) -> List[Dict]:
        """Search YouTube with quota-aware error handling."""
        thread_id = threading.current_thread().name
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[{thread_id}] Searching YouTube for: {query}")
                
                # Rebuild client on retries (thread-safe)
                if attempt > 0:
                    with self._lock:
                        self.youtube = build('youtube', 'v3', developerKey=self._api_key)
                    logger.info(f"[{thread_id}] Rebuilt client (attempt {attempt + 1})")
                
                search_response = self.youtube.search().list(
                    q=query,
                    part='id,snippet',
                    maxResults=max_results,
                    type='video',
                    videoEmbeddable='true',
                    videoSyndicated='true',
                    relevanceLanguage='en',
                    safeSearch='strict',
                    videoDuration='medium'
                ).execute()
                
                videos = []
                for item in search_response.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    video = {
                        'id': video_id,
                        'title': snippet['title'],
                        'channel': snippet['channelTitle'],
                        'thumbnail': snippet['thumbnails']['high']['url'],
                        'embed_url': f'https://www.youtube.com/embed/{video_id}'
                    }
                    videos.append(video)
                
                logger.info(f"[{thread_id}] Found {len(videos)} videos")
                return videos
                
            except HttpError as e:
                # Check for quota exceeded (403)
                if e.resp.status == 403 and 'quotaExceeded' in str(e):
                    logger.error(
                        f"[{thread_id}] ⚠️ YouTube API QUOTA EXCEEDED - "
                        "Returning empty results for remaining topics"
                    )
                    # Don't retry quota errors - they won't succeed
                    return []
                else:
                    logger.error(f"[{thread_id}] YouTube API error: {str(e)}")
                    return []
                    
            except (SSLError, IncompleteRead) as e:
                error_type = type(e).__name__
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"[{thread_id}] Connection error (attempt {attempt + 1}/{max_retries}): "
                        f"{error_type}: {str(e)} - retrying in {backoff}s"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"[{thread_id}] Failed after {max_retries} attempts: {error_type}"
                    )
                    return []
                    
            except AttributeError as e:
                # Catch the 'NoneType has no attribute read' error
                if "'NoneType' object has no attribute 'read'" in str(e):
                    logger.error(
                        f"[{thread_id}] HTTP connection died - rebuilding client"
                    )
                    if attempt < max_retries - 1:
                        with self._lock:
                            self.youtube = build('youtube', 'v3', developerKey=self._api_key)
                        time.sleep(2)
                    else:
                        return []
                elif "'YouTubeClient' object has no attribute" in str(e):
                    # This shouldn't happen anymore with _api_key fix
                    logger.error(f"[{thread_id}] Client attribute error: {str(e)}")
                    return []
                else:
                    raise  # Re-raise unexpected AttributeErrors
                    
            except Exception as e:
                error_type = type(e).__name__
                logger.error(
                    f"[{thread_id}] Unexpected error: {error_type}: {str(e)}", 
                    exc_info=True
                )
                return []
        
        return []