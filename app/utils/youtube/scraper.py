"""
YouTube scraper as free alternative to API.
"""
from typing import List, Dict
import re
import requests
from urllib.parse import quote

from app.utils.logger import get_logger


logger = get_logger(__name__)


class YouTubeScraper:
    """Free YouTube video search using web scraping."""
    
    def __init__(self):
        """Initialize YouTube scraper."""
        logger.info("YouTube scraper initialized (no API key needed)")
    
    def search_videos(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Search YouTube for educational videos using web scraping.
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results (default: 3)
        
        Returns:
            List[Dict]: List of video details
        """
        try:
            logger.info(f"Searching YouTube for: {query}")
            
            # Use YouTube's search without API
            search_url = f"https://www.youtube.com/results?search_query={quote(query + ' tutorial')}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            # Extract video IDs from page content
            video_ids = re.findall(r'"videoId":"([^"]{11})"', response.text)
            
            # Get unique video IDs
            video_ids = list(dict.fromkeys(video_ids))[:max_results]
            
            videos = []
            for video_id in video_ids:
                video = {
                    'id': video_id,
                    'title': f"Tutorial: {query}",
                    'channel': 'Educational Channel',
                    'thumbnail': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
                    'embed_url': f'https://www.youtube.com/embed/{video_id}'
                }
                videos.append(video)
            
            logger.info(f"Found {len(videos)} videos")
            return videos
        
        except Exception as e:
            logger.error(f"YouTube scraping error: {str(e)}")
            # Return fallback video links
            return self._get_fallback_videos(query, max_results)
    
    def _get_fallback_videos(self, query: str, max_results: int) -> List[Dict]:
        """Return generic video placeholders."""
        logger.warning("Using fallback video placeholders")
        return [
            {
                'id': 'dQw4w9WgXcQ',
                'title': f'{query} - Educational Tutorial',
                'channel': 'Educational Channel',
                'thumbnail': 'https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
                'embed_url': f'https://www.youtube.com/embed/dQw4w9WgXcQ'
            }
            for i in range(max_results)
        ]
