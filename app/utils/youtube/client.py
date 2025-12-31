"""
YouTube API client for video search and retrieval.
"""
from typing import List, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.utils.logger import get_logger


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
        
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        logger.info("YouTube client initialized")
    
    def search_videos(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Search YouTube for educational videos.
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results (default: 3)
        
        Returns:
            List[Dict]: List of video details with structure:
                {
                    'id': str,
                    'title': str,
                    'channel': str,
                    'thumbnail': str,
                    'embed_url': str
                }
        
        Raises:
            Exception: If API call fails
        """
        try:
            logger.info(f"Searching YouTube for: {query}")
            
            # Search request
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                videoEmbeddable='true',
                videoSyndicated='true',
                relevanceLanguage='en',
                safeSearch='strict',
                videoDuration='medium'  # 4-20 minutes
            ).execute()
            
            # Parse results
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
            
            logger.info(f"Found {len(videos)} videos")
            return videos
        
        except HttpError as e:
            logger.error(f"YouTube API error: {str(e)}")
            raise Exception(f"YouTube search failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
            raise
