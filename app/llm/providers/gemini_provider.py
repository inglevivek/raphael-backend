"""
Gemini LLM Provider - Google's Gemini AI.
"""

import json
import re
from typing import Optional
import google.generativeai as genai
from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger
from app.exceptions import ValidationException

logger = get_logger(__name__)

class GeminiProvider(BaseLLMProvider):
    """Provider for Google Gemini API."""

    def __init__(self, api_key: str, model: str = 'gemini-2.5-flash', **kwargs):
        super().__init__(api_key, model, **kwargs)

        if not api_key:
            raise ValueError("Gemini API key is required")

        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model)

        logger.info(f"Gemini provider initialized with model: {self.model}")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text response from Gemini API."""
        try:
            logger.info("Generating text response from Gemini")
            response = self.client.generate_content(prompt)

            if not response or not response.text:
                raise Exception("Empty response from Gemini API")

            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise Exception(f"Failed to generate content: {str(e)}")

    def generate_json(self, prompt: str, **kwargs) -> dict:
        """Generate and parse JSON response from Gemini API."""
        try:
            logger.info("Generating JSON response from Gemini")
            text_response = self.generate(prompt)

            # Extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*({.+?})\s*```', text_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = text_response

            # Parse JSON
            parsed = json.loads(json_str)
            logger.info("Successfully parsed JSON response from Gemini")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            raise ValidationException(f"Invalid JSON response from Gemini: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating JSON: {str(e)}")
            raise
