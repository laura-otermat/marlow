from typing import Any

from openai import OpenAI

from app.config import settings
from app.models.memory import Memory


def create_openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to call the OpenAI API.")
    return OpenAI(api_key=settings.openai_api_key)


def extract_memory(text: str, *, openai_client: Any | None = None) -> Memory:
    if openai_client is None:
        openai_client = create_openai_client()

    response = openai_client.responses.parse(
        model="gpt-5-mini",
        input=[
            {
                "role": "system",
                "content": """
You are Marlow, a household memory assistant.

Extract useful household facts from user messages.

Only create memories for information that would help a household assistant later.
Focus on household context such as birthdays, school needs, preferences, routines,
events, purchases, and seasonal tasks.

Do not create memories for private personal information, confidential details, or
anything that should remain between two people. Do not create memories for
greetings or casual conversation.

Examples:
- Clothing sizes
- School preferences
- Food expiry information
- Important dates
- Family routines
- Preferences
- Household purchases
- Seasonal tasks
""",
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        text_format=Memory,
    )

    memory = response.output_parsed
    if memory is None:
        raise ValueError("The model did not return a structured memory.")
    return memory
