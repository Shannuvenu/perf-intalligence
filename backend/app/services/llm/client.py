from app.core.config import Settings, get_settings
from app.services.llm.base import LlmSynthesisProvider
from app.services.llm.mock_llm import MockLlmProvider
from app.services.llm.openai_llm import OpenAiLlmProvider


def get_llm_provider(
    settings: Settings | None = None,
) -> LlmSynthesisProvider:

    settings = settings or get_settings()

    if settings.LLM_PROVIDER == "mock":
        return MockLlmProvider()

    if settings.LLM_PROVIDER == "groq":
        return OpenAiLlmProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            base_url="https://api.groq.com/openai/v1",
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}"
    )