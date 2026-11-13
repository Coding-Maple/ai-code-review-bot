import os

from google import genai
from google.genai import types

from review_bot.prompt import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "gemini-3.5-flash"


def review(diff: str) -> str:
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY environment variable is not set")

    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=120_000,                               # milliseconds
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
    )

    response = client.models.generate_content(
        model=model,
        contents=build_user_prompt(diff),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        ),
    )

    if not response.text:
        raise RuntimeError("LLM returned an empty response")
    return response.text
