"""
Ollama LLM Provider - Local LLM inference using Ollama.
"""

import json
import re
import requests
from typing import Optional
from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger
from app.exceptions import ValidationException

logger = get_logger(__name__)

class OllamaProvider(BaseLLMProvider):
    """Provider for Ollama local LLM inference."""

    def __init__(self, api_key: str = None, model: str = 'llama2', 
                 base_url: str = 'http://localhost:11434', **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.base_url = base_url.rstrip('/')
        self.temperature = kwargs.get('temperature', 0.8)

        logger.info(f"Ollama provider initialized with model: {self.model} at {self.base_url}")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text response using Ollama."""
        try:
            url = f"{self.base_url}/api/generate"

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', self.temperature)
                }
            }

            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()

            result = response.json()
            text = result.get('response', '').strip()

            logger.info(f"Generated {len(text)} characters from Ollama")
            return text

        except Exception as e:
            logger.error(f"Ollama API error: {str(e)}")
            raise Exception(f"Failed to generate content: {str(e)}")

    def generate_json(self, prompt: str, **kwargs) -> dict:
        """Generate and parse JSON response using Ollama."""
        try:
            json_prompt = f"""{prompt}

IMPORTANT: Return ONLY valid JSON. No markdown, no explanations, just pure JSON."""

            text_response = self.generate(json_prompt, **kwargs)
            json_str = self._extract_json(text_response)
            parsed = json.loads(json_str)

            logger.info("Successfully parsed JSON response from Ollama")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            raise ValidationException(f"Invalid JSON from Ollama: {e}")
        except Exception as e:
            logger.error(f"Error generating JSON: {str(e)}")
            raise

    def generate_with_context(self, messages: list, **kwargs) -> str:
        """Generate response with conversation context using Ollama chat API."""
        try:
            url = f"{self.base_url}/api/chat"

            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', self.temperature)
                }
            }

            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()

            result = response.json()
            text = result.get('message', {}).get('content', '').strip()

            logger.info(f"Generated {len(text)} characters with context from Ollama")
            return text

        except Exception as e:
            logger.error(f"Ollama context generation error: {str(e)}")
            raise

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text response."""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        start = text.find('{')
        if start != -1:
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]

        return text
