from app.core.config import Settings, get_settings
from app.services.llm.base import LlmSynthesisProvider
from app.services.llm.mock_llm import MockLlmProvider
from app.services.llm.openai_llm import OpenAiLlmProvider


def get_llm_provider(settings: Settings | None = None) -> LlmSynthesisProvider:
    settings = settings or get_settings()
    if settings.LLM_PROVIDER == "mock":
        return MockLlmProvider()
    return OpenAiLlmProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
