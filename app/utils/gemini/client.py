"""
Google Gemini API client for AI-powered content generation.
"""
import json
import re
from typing import Optional

import google.generativeai as genai

from app.utils.logger import get_logger
from app.exceptions import ValidationException


logger = get_logger(__name__)


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini client with API key.
        
        Args:
            api_key (str): Google Gemini API key
        
        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("Gemini client initialized")
    
    def generate(self, prompt: str) -> str:
        """
        Generate text response from Gemini API.
        
        Args:
            prompt (str): Input prompt for generation
        
        Returns:
            str: Generated text response
        
        Raises:
            Exception: If API call fails
        """
        try:
            logger.info("Generating text response from Gemini")
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini API")
            
            return response.text.strip()
        
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise Exception(f"Failed to generate content: {str(e)}")
    
    def generate_json(self, prompt: str) -> dict:
        """
        Generate and parse JSON response from Gemini API.
        Automatically extracts JSON from markdown code blocks.
        
        Args:
            prompt (str): Input prompt for generation
        
        Returns:
            dict: Parsed JSON response
        
        Raises:
            ValidationException: If response is not valid JSON
        """
        try:
            logger.info("Generating JSON response from Gemini")
            text_response = self.generate(prompt)
            
            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'``````', text_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = text_response
            
            # Parse JSON
            parsed = json.loads(json_str)
            logger.info("Successfully parsed JSON response")
            return parsed
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            logger.debug(f"Raw response: {text_response[:500]}")
            raise ValidationException(f"Invalid JSON response from AI: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error generating JSON: {str(e)}")
            raise
