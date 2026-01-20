"""
Groq LLM Provider - Fast AI inference using Groq.
"""

import json
import re
import time
from typing import Optional
from groq import Groq
from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger
from app.exceptions import ValidationException

logger = get_logger(__name__)

class GroqProvider(BaseLLMProvider):
    """Provider for Groq API."""

    def __init__(self, api_key: str = None, model: str = 'groq/compound-mini', **kwargs):
        super().__init__(api_key, model, **kwargs)

        if not api_key:
            self.client = Groq()  # Use env GROQ_API_KEY
        else:
            self.client = Groq(api_key=api_key)

        self.temperature = kwargs.get('temperature', 1.0)
        self.top_p = kwargs.get('top_p', 1.0)
        self.stream = kwargs.get('stream', True)

        logger.info(f"Groq provider initialized with model: {self.model}")

    def generate(self, prompt: str, max_retries: int = 3, **kwargs) -> str:
        """Generate text response from Groq API."""
        for attempt in range(max_retries):
            try:
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
                    temperature=kwargs.get('temperature', self.temperature),
                    top_p=kwargs.get('top_p', self.top_p),
                    stream=self.stream,
                    stop=None
                )

                # Collect streamed response
                full_response = ""
                if self.stream:
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        full_response += content
                else:
                    full_response = completion.choices[0].message.content

                text = full_response.strip()
                logger.info(f"Generated {len(text)} characters from Groq")
                return text

            except Exception as e:
                logger.error(f"Groq API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise

        return ""

    def generate_json(self, prompt: str, validate_outline: bool = False, max_retries: int = 3, **kwargs) -> dict:
        """Generate and parse JSON response from Groq API."""
        for attempt in range(max_retries):
            try:
                temperature = 0.2 + (attempt * 0.1)

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
                    temperature=temperature,
                    top_p=0.9,
                    stream=False,
                    stop=None
                )

                text_response = completion.choices[0].message.content.strip()
                json_str = self._extract_json(text_response)
                parsed = json.loads(json_str)

                logger.info("Successfully parsed JSON response from Groq")
                return parsed

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    raise ValidationException(f"Invalid JSON after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Error generating JSON: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    raise

        return {}

    def generate_with_context(self, messages: list, **kwargs) -> str:
        """Generate response with full conversation context."""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get('temperature', self.temperature),
                top_p=kwargs.get('top_p', self.top_p),
                stream=self.stream,
                stop=None
            )

            full_response = ""
            if self.stream:
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    full_response += content
            else:
                full_response = completion.choices[0].message.content

            return full_response.strip()

        except Exception as e:
            logger.error(f"Error in context generation: {str(e)}")
            raise

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text with balanced brace parsing."""
        # Clean markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        # Balanced brace counting
        json_objects = []
        start = None
        depth = 0

        for i, char in enumerate(text):
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    json_str = text[start:i+1]
                    try:
                        json.loads(json_str)
                        json_objects.append(json_str)
                    except:
                        pass
                    start = None

        if json_objects:
            return max(json_objects, key=len)

        # Try the whole text
        try:
            json.loads(text)
            return text
        except:
            raise ValidationException("No valid JSON found in response")
