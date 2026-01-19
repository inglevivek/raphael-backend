"""
Groq API client for AI-powered content generation.
Non-streaming mode for reliable complete responses.
"""
import json
import re
import time
from typing import Optional

from groq import Groq

from app.utils.logger import get_logger
from app.exceptions import ValidationException


logger = get_logger(__name__)


class GroqClient:
    """Client for interacting with Groq API (non-streaming)."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize Groq client with API key.
        
        Args:
            api_key (str, optional): Groq API key (uses env if not provided)
        """
        if not api_key:
            self.client = Groq()
        else:
            self.client = Groq(api_key=api_key)
        
        self.model = "openai/gpt-oss-20b"  # More reliable than openai model
        
        logger.info(f"Groq client initialized with model: {self.model}")
    
    def generate(self, prompt: str, max_retries: int = 3) -> str:
        """
        Generate text response from Groq API (non-streaming).
        
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
                logger.info(f"Generating text from Groq (attempt {attempt + 1}/{max_retries})")
                
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert curriculum designer and educator. Provide clear, structured responses."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.5,  # Low temperature for consistent output
                    max_tokens=8192,
                    top_p=0.9,
                    stream=False,  # Explicitly disable streaming
                    stop=None
                )
                
                # Get complete response
                text = completion.choices[0].message.content.strip()
                logger.info(f"Generated {len(text)} characters")
                return text
            
            except Exception as e:
                logger.error(f"Groq API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Failed to generate content: {str(e)}")
    
    def generate_json(self, prompt: str, max_retries: int = 3) -> dict:
        """
        Generate and parse JSON response from Groq API (non-streaming).
        
        Args:
            prompt (str): Input prompt for generation
            max_retries (int): Maximum number of retry attempts
        
        Returns:
            dict: Parsed JSON response
        
        Raises:
            ValidationException: If response is not valid JSON
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating JSON from Groq (attempt {attempt + 1}/{max_retries})")
                
                # Enhanced prompt for JSON
                json_prompt = f"""{prompt}

                IMPORTANT RULES:
                1. Return ONLY valid JSON - no markdown, no code blocks, no explanations
                2. Use double quotes for all strings
                3. Ensure all braces {{}} and brackets [] are properly closed
                4. No trailing commas
                5. Complete the entire JSON structure before stopping"""
                
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a JSON generator. Return ONLY valid, complete JSON objects. No markdown formatting."
                        },
                        {
                            "role": "user",
                            "content": json_prompt
                        }
                    ],
                    temperature=0.2,  # Very low for consistent JSON
                    max_tokens=4096,
                    top_p=0.9,
                    stream=False,  # Non-streaming for complete responses
                    stop=None
                )
                
                text_response = completion.choices[0].message.content.strip()
                logger.info(f"Received {len(text_response)} characters")
                
                # Extract JSON from response
                json_str = self._extract_json(text_response)
                
                # Parse JSON
                parsed = json.loads(json_str)
                logger.info("Successfully parsed JSON response")
                return parsed
            
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if text_response:
                    logger.error(f"Response: {text_response[:500]}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying JSON generation...")
                    time.sleep(2)
                else:
                    raise ValidationException(f"Invalid JSON after {max_retries} attempts: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error generating JSON: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise
    
    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text using brace-counting algorithm.
        Handles deeply nested structures correctly.
        
        Args:
            text (str): Text containing JSON
        
        Returns:
            str: Extracted JSON string
        
        Raises:
            ValidationException: If no valid JSON found
        """
        # Remove markdown code blocks first
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Find ALL complete JSON objects using brace counting
        json_candidates = []
        depth = 0
        start_idx = None
        
        for i, char in enumerate(text):
            if char == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    # Found a complete JSON object
                    json_str = text[start_idx:i+1]
                    try:
                        # Validate it's actually valid JSON
                        json.loads(json_str)
                        json_candidates.append(json_str)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON
                    start_idx = None
        
        if not json_candidates:
            logger.warning("No valid JSON objects found in response")
            return text  # Fallback to original text
        
        # Return the LARGEST JSON object (most complete)
        largest = max(json_candidates, key=len)
        logger.info(f"Extracted JSON object ({len(largest)} chars from {len(json_candidates)} candidates)")
        
        return largest
