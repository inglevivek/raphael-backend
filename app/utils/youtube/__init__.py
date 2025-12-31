"""
YouTube utilities.
"""
import os

# Use scraper if no API key, otherwise use API client
youtube_api_key = os.environ.get('YOUTUBE_API_KEY')

if youtube_api_key:
    from app.utils.youtube.client import YouTubeClient
else:
    from app.utils.youtube.scraper import YouTubeScraper as YouTubeClient

__all__ = ['YouTubeClient']
