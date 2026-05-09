import logging
import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

log = logging.getLogger(__name__)

_DEFAULTS = {
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
}


def get_llm() -> BaseChatModel:
    provider = os.environ.get("LLM_PROVIDER") or _DEFAULTS["provider"]
    model = os.environ.get("LLM_MODEL") or _DEFAULTS["model"]

    if not os.environ.get("LLM_PROVIDER"):
        log.warning("LLM_PROVIDER not set, defaulting to %s/%s", provider, model)

    return init_chat_model(model=model, model_provider=provider)
