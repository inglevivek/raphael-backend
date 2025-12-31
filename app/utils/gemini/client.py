"""
Google Gemini API client for AI-powered content generation.
"""
import json
import re
import time
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
        
        # Configure safety settings to be more permissive for educational content
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Configure generation settings
        self.generation_config = {
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 64000,
        }
        
        self.model = genai.GenerativeModel(
            'gemini-3-flash-preview',
            safety_settings=self.safety_settings,
            generation_config=self.generation_config
        )
        
        logger.info("Gemini client initialized with safety settings")
    
    def generate(self, prompt: str, max_retries: int = 3) -> str:
        """
        Generate text response from Gemini API with retry logic.
        
        Args:
            prompt (str): Input prompt for generation
            max_retries (int): Maximum number of retry attempts
        
        Returns:
            str: Generated text response
        
        Raises:
            Exception: If API call fails after all retries
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating text response from Gemini (attempt {attempt + 1}/{max_retries})")
                
                response = self.model.generate_content(prompt)
                
                # Check if response was blocked
                if not response or not response.text:
                    if hasattr(response, 'prompt_feedback'):
                        logger.error(f"Response blocked: {response.prompt_feedback}")
                        if response.prompt_feedback.block_reason:
                            raise Exception(f"Content blocked: {response.prompt_feedback.block_reason}")
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"Empty response, retrying in {2 ** attempt} seconds...")
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        raise Exception("Empty response from Gemini API after all retries")
                
                text = response.text.strip()
                logger.info(f"Generated {len(text)} characters")
                return text
            
            except Exception as e:
                logger.error(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Failed to generate content after {max_retries} attempts: {str(e)}")
    
    def generate_json(self, prompt: str, max_retries: int = 3) -> dict:
        """
        Generate and parse JSON response from Gemini API.
        Automatically extracts JSON from markdown code blocks.
        
        Args:
            prompt (str): Input prompt for generation
            max_retries (int): Maximum number of retry attempts
        
        Returns:
            dict: Parsed JSON response
        
        Raises:
            ValidationException: If response is not valid JSON
        """
        try:
            logger.info("Generating JSON response from Gemini")
            text_response = self.generate(prompt, max_retries)
            
            if not text_response:
                raise ValidationException("Empty response from Gemini API")
            
            # Log first 200 chars for debugging
            logger.debug(f"Raw response preview: {text_response[:200]}...")
            
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                logger.info("Extracted JSON from markdown code block")
            else:
                # Try to find JSON object in response
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    logger.info("Extracted JSON object from response")
                else:
                    json_str = text_response
            
            # Parse JSON
            parsed = json.loads(json_str)
            logger.info("Successfully parsed JSON response")
            return parsed
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            logger.error(f"Response content: {text_response[:500]}")
            raise ValidationException(f"Invalid JSON response from AI: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error generating JSON: {str(e)}")
            raise
