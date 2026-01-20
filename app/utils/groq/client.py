"""
Groq API client for fast AI-powered content generation.
Uses streaming with OpenAI GPT model.
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
    """Client for interacting with Groq API with streaming support."""

    def __init__(self, api_key: str = None):
        """
        Initialize Groq client with API key.

        Args:
            api_key (str, optional): Groq API key (uses env if not provided)

        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            # Groq client will use GROQ_API_KEY from environment
            self.client = Groq()
        else:
            self.client = Groq(api_key=api_key)

        # Use OpenAI GPT model as specified
        self.model = "llama-3.1-8b-instant"

        logger.info(f"Groq client initialized with model: {self.model}")

    def generate(self, prompt: str, max_retries: int = 3, stream: bool = True) -> str:
        """
        Generate text response from Groq API with streaming support.

        Args:
            prompt (str): Input prompt for generation
            max_retries (int): Maximum number of retry attempts
            stream (bool): Whether to use streaming (default: True)

        Returns:
            str: Generated text response

        Raises:
            Exception: If API call fails after all retries
        """
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Generating text response from Groq "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

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
                    temperature=1,
                    top_p=1,
                    stream=stream,
                    stop=None
                )

                # Collect streamed response
                full_response = ""
                if stream:
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        full_response += content
                else:
                    full_response = completion.choices[0].message.content

                text = full_response.strip()
                logger.info(f"Generated {len(text)} characters")
                return text

            except Exception as e:
                logger.error(f"Groq API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 10 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Failed to generate content after {max_retries} attempts: {str(e)}")

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text with robust balanced-brace parsing.

        Args:
            text (str): Text containing JSON

        Returns:
            str: Extracted JSON string

        Raises:
            ValidationException: If no valid JSON found
        """
        # Clean up markdown formatting
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        # Strategy 1: Balanced brace counting (handles nested JSON)
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
                    # Validate it's parseable before adding
                    try:
                        json.loads(json_str)
                        json_objects.append(json_str)
                    except:
                        pass
                    start = None

        if json_objects:
            # Return the largest valid JSON object
            largest = max(json_objects, key=len)
            logger.info(f"Extracted largest JSON object ({len(largest)} chars from {len(json_objects)} candidates)")
            return largest

        # Strategy 2: Try the whole text (might already be clean JSON)
        try:
            json.loads(text)
            logger.info("Text is already valid JSON")
            return text
        except:
            pass

        # Strategy 3: No valid JSON found
        logger.error("No valid JSON objects found in response")
        raise ValidationException("No JSON found in AI response")

    def _validate_outline_json(self, parsed: dict, attempt: int, max_retries: int) -> bool:
        """
        Validate that outline JSON has required 3-module structure.

        🔧 FIX: Adds validation to ensure complete course outline.

        Args:
            parsed (dict): Parsed JSON object
            attempt (int): Current attempt number
            max_retries (int): Maximum retry attempts

        Returns:
            bool: True if valid, False if should retry
        """
        # Check for modules key
        if 'modules' not in parsed:
            logger.warning("JSON missing 'modules' key")
            return False

        modules = parsed['modules']

        # Check modules is a list
        if not isinstance(modules, list):
            logger.warning("'modules' is not a list")
            return False

        # Check for 3 modules
        if len(modules) < 3:
            logger.warning(
                f"Only {len(modules)} modules found (expected 3). "
                f"Attempt {attempt}/{max_retries}"
            )
            # On last attempt, accept what we have
            if attempt >= max_retries:
                logger.info("Last attempt - accepting incomplete outline")
                return True
            return False

        # Validate each module has chapters
        for i, module in enumerate(modules, 1):
            if 'chapters' not in module or not module['chapters']:
                logger.warning(f"Module {i} missing chapters")
                return False

        logger.info(f"✅ Valid outline: {len(modules)} modules with chapters")
        return True

    def generate_json(
        self, 
        prompt: str, 
        max_retries: int = 3,
        validate_outline: bool = False
    ) -> dict:
        """
        Generate and parse JSON response from Groq API.

        🔧 FIX: Added brace-counting extraction and outline validation.

        Args:
            prompt (str): Input prompt for generation
            max_retries (int): Maximum number of retry attempts
            validate_outline (bool): If True, validate 3-module structure

        Returns:
            dict: Parsed JSON response

        Raises:
            ValidationException: If response is not valid JSON
        """
        for attempt in range(max_retries):
            try:
                # Progressive temperature increase on retries
                temperature = 0.2 + (attempt * 0.1)

                logger.info(
                    f"Generating JSON from Groq "
                    f"(attempt {attempt + 1}/{max_retries}, temp={temperature})"
                )

                # Enhanced JSON prompt
                json_prompt = f"""{prompt}

                IMPORTANT RULES:
                1. Return ONLY valid JSON - no markdown, no code blocks, no explanations
                2. Use double quotes for all strings
                3. Ensure all braces {{}} and brackets [] are properly closed
                4. No trailing commas
                5. Complete the entire JSON structure before stopping"""

                # Generate with custom temperature
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
                logger.info(f"Received {len(text_response)} characters")

                # 🔧 FIX: Use brace-counting extraction
                json_str = self._extract_json(text_response)

                # Parse JSON
                parsed = json.loads(json_str)
                logger.info("Successfully parsed JSON response")

                # 🔧 FIX: Validate outline structure if requested
                if validate_outline:
                    if not self._validate_outline_json(parsed, attempt + 1, max_retries):
                        if attempt < max_retries - 1:
                            logger.info("Retrying due to incomplete outline...")
                            time.sleep(10)
                            continue
                        else:
                            logger.error("All attempts produced incomplete outlines")

                return parsed

            except json.JSONDecodeError as e:
                logger.error(
                    f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if 'text_response' in locals():
                    logger.error(f"Response preview: {text_response[:500]}")

                if attempt < max_retries - 1:
                    logger.info("Retrying JSON generation...")
                    time.sleep(5 * (attempt + 1))
                else:
                    raise ValidationException(
                        f"Invalid JSON after {max_retries} attempts: {e}"
                    )

            except Exception as e:
                logger.error(f"Error generating JSON: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    raise

        return {}

    def generate_with_context(self, messages: list, stream: bool = True) -> str:
        """
        Generate response with full conversation context.

        Useful for multi-turn conversations.

        Args:
            messages (list): List of message dicts with 'role' and 'content'
            stream (bool): Whether to use streaming

        Returns:
            str: Generated response

        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"}
            ]
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=1,
                top_p=1,
                stream=stream,
                stop=None
            )

            # Collect streamed response
            full_response = ""
            if stream:
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    full_response += content
            else:
                full_response = completion.choices[0].message.content

            return full_response.strip()

        except Exception as e:
            logger.error(f"Error in context generation: {str(e)}")
            raise
