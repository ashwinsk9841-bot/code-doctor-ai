"""
AI Provider abstraction for Code Doctor AI.

Centralizes AI access so providers, models, and error classification live in
one place. API keys are read from configuration/environment only — never
hardcoded. Provider failures (401/402/403/429/quota/model-unavailable) are
classified distinctly so the UI can show correct messages instead of blaming
the user's code.
"""
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Base class for AI provider environment/configuration errors."""

    def __init__(self, message: str, kind: str = "provider"):
        super().__init__(message)
        self.kind = kind
        self.message = message


class AuthenticationError(ProviderError):
    def __init__(self, message="AI provider authentication failed. Check your API key."):
        super().__init__(message, "authentication")


class QuotaExceededError(ProviderError):
    def __init__(self, message="AI provider quota or credits exhausted."):
        super().__init__(message, "quota")


class RateLimitedError(ProviderError):
    def __init__(self, message="AI provider rate limit hit. Try again shortly."):
        super().__init__(message, "rate_limit")


class ModelUnavailableError(ProviderError):
    def __init__(self, message="AI model unavailable."):
        super().__init__(message, "model_unavailable")


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    provider_name = "base"

    @abstractmethod
    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        """Return a completion from the model."""

    @abstractmethod
    def _normalize_model(self) -> str:
        ...

    # ----- shared helpers -----
    def analyze_code(self, code: str, language: str, analysis_type: str = "full",
                     file_context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Analyze code and return normalized structured results."""
        system = (
            "You are Code Doctor AI, a senior code reviewer. Analyze the provided "
            "source and return ONLY a valid JSON object. Do not include markdown, "
            "code fences, or prose outside the JSON.\n\n"
            'Schema: {"issues": [{"title": str, "category": one of '
            'BUG,SECURITY,DEPENDENCY,PERFORMANCE,CODE_QUALITY,CONFIGURATION,TEST,OTHER, '
            '"severity": one of CRITICAL,HIGH,MEDIUM,LOW,INFO, '
            '"line": int|null, "line_end": int|null, '
            '"description": str, "why_it_matters": str, "evidence": str, '
            '"recommended_fix": str, "fixable": bool, "confidence": number 0..1}], '
            '"overall_quality": "CRITICAL|POOR|FAIR|GOOD|EXCELLENT"} '
            "Only report genuine, code-grounded issues with high confidence. "
            "Do not invent vulnerabilities that are not present."
        )
        context = f"File context: language={language}\n"
        if file_context:
            for fc in file_context:
                context += f"\n--- {fc.get('path')} ---\n{fc.get('content', '')[:4000]}\n"
        else:
            context += f"\n--- source ---\n{code}\n"
        user_message = f"Analyze the following source code:\n\n{context}"
        raw = self.complete(system, user_message, max_tokens=4000)
        return self._extract_json(raw, default={
            "issues": [], "overall_quality": "UNKNOWN",
        })

    def fix_code(self, code: str, language: str, issues: list) -> str:
        """Generate a corrected version of the code."""
        issues_text = "\n".join(
            f"- [{i.get('category','OTHER')}][{i.get('severity','MEDIUM')}] "
            f"{i.get('title','Issue')}: {i.get('description','')}"
            for i in issues
        )
        system = (
            "You are Code Doctor AI. Rewrite ONLY the provided source to fix the "
            "listed issues. Preserve all unchanged behavior, formatting, and unrelated "
            "code. Return ONLY the corrected source inside a single fenced code block "
            "with no extra commentary."
        )
        user_message = (
            f"Original {language} code:\n```{language}\n{code}\n```\n\n"
            f"Issues to fix:\n{issues_text}\n\nReturn the complete corrected code."
        )
        return self._strip_fence(self.complete(system, user_message, max_tokens=6000), language)

    def generate_tests(self, code: str, language: str, framework: Optional[str] = None) -> str:
        """Generate test cases for the given code."""
        system = (
            "You are Code Doctor AI. Write a concise but meaningful test suite for the "
            "provided code that exercises normal, edge, and error cases. Follow the "
            f"{framework or 'project'} conventions. Return ONLY the test code inside a "
            "single fenced code block."
        )
        user_message = (
            f"Source ({language}):\n```{language}\n{code}\n```\n\n"
            "Write tests. Return only the code."
        )
        return self._strip_fence(self.complete(system, user_message, max_tokens=4000), language)

    def explain_issue(self, issue: Dict[str, Any], code_snippet: str) -> str:
        """Human-readable explanation of a specific issue."""
        system = (
            "You are Code Doctor AI. Explain the reported code issue clearly and "
            "concisely, in plain language a developer can act on. Do not add "
            "unrelated advice."
        )
        user_message = (
            f"Issue title: {issue.get('title')}\n"
            f"Category: {issue.get('category')}\nSeverity: {issue.get('severity')}\n"
            f"Description: {issue.get('description')}\n\n"
            f"Relevant code:\n{code_snippet}\n\nExplain the problem and the fix."
        )
        return self.complete(system, user_message, max_tokens=800)

    # ----- parsing helpers -----
    def _extract_json(self, text: str, default: Dict[str, Any]) -> Dict[str, Any]:
        if not text:
            return default
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return default
        try:
            data = json.loads(match.group())
            return data if isinstance(data, dict) else default
        except Exception:
            return default

    @staticmethod
    def _strip_fence(text: str, language: str) -> str:
        pattern = r"```(?:[a-zA-Z0-9_+-]*)\s*\n(.*?)```"
        m = re.search(pattern, text, re.DOTALL)
        if m:
            return m.group(1).strip()
        return text.strip()


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str = ""):
        if not api_key:
            raise AuthenticationError("Anthropic API key is required.")
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-20250514"
        try:
            import anthropic
        except ImportError:
            raise ProviderError(
                "The 'anthropic' package is not installed. Run: pip install anthropic",
                "dependency",
            )
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except Exception as e:
            raise self._classify(e)

    @staticmethod
    def _classify(e: Exception) -> ProviderError:
        msg = str(e)
        code = getattr(getattr(e, "status_code", None), "code", None) or getattr(e, "status_code", None)
        if code == 401 or "authentication" in msg.lower() or "invalid x-api-key" in msg.lower():
            return AuthenticationError()
        if code == 402 or "credit" in msg.lower() or "billing" in msg.lower():
            return QuotaExceededError()
        if code == 403 and "permission" in msg.lower():
            return AuthenticationError("AI provider rejected the request (403). Check permissions or key.")
        if code == 429 or "rate" in msg.lower():
            return RateLimitedError()
        if "not_found" in msg.lower() or ("model" in msg.lower() and "not" in msg.lower()):
            return ModelUnavailableError()
        return ProviderError(f"Anthropic API error: {msg}", "provider")


class OpenCodeZenProvider(AIProvider):
    """OpenCode Zen provider (free models like Big Pickle).

    OpenCode Zen exposes an OpenAI-compatible chat completions endpoint, so this
    reuses the ``openai`` SDK pointed at ``https://opencode.ai/zen/v1``. The
    default model is the free **Big Pickle**; no paid credits are required.
    """

    provider_name = "opencode_zen"
    DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
    DEFAULT_MODEL = "big-pickle"

    def __init__(self, api_key: str, model: str = "", base_url: str = ""):
        if not api_key:
            raise AuthenticationError("OpenCode Zen API key is required.")
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.DEFAULT_BASE_URL
        try:
            import openai
        except ImportError:
            raise ProviderError(
                "The 'openai' package is not installed. Run: pip install openai",
                "dependency",
            )
        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key, base_url=self.base_url)

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise self._classify(e)

    @staticmethod
    def _classify(e: Exception) -> ProviderError:
        msg = str(e)
        code = getattr(getattr(e, "status_code", None), "code", None) or getattr(e, "status_code", None)
        if code == 401 or "authentication" in msg.lower() or "invalid api key" in msg.lower():
            return AuthenticationError()
        if code == 402 or "insufficient_quota" in msg.lower() or "billing" in msg.lower() or "credit" in msg.lower():
            return QuotaExceededError()
        if code == 429 or "rate limit" in msg.lower():
            return RateLimitedError()
        if code == 404 or ("model" in msg.lower() and ("not found" in msg.lower() or "does not exist" in msg.lower() or "not_found" in msg.lower())):
            return ModelUnavailableError()
        if code == 403:
            return ProviderError("AI provider rejected the request (403). Check permissions.", "provider")
        return ProviderError(f"OpenCode Zen API error: {msg}", "provider")


class OpenAIProvider(AIProvider):
    """OpenAI provider."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str = ""):
        if not api_key:
            raise AuthenticationError("OpenAI API key is required.")
        self.api_key = api_key
        self.model = model or "gpt-4o"
        try:
            import openai
        except ImportError:
            raise ProviderError(
                "The 'openai' package is not installed. Run: pip install openai",
                "dependency",
            )
        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key)

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise self._classify(e)

    @staticmethod
    def _classify(e: Exception) -> ProviderError:
        msg = str(e)
        code = getattr(getattr(e, "status_code", None), "code", None) or getattr(e, "status_code", None)
        if code == 401 or "authentication" in msg.lower():
            return AuthenticationError()
        if code == 402 or "insufficient_quota" in msg.lower() or "billing" in msg.lower():
            return QuotaExceededError()
        if code == 429 or "rate limit" in msg.lower():
            return RateLimitedError()
        if code == 404 or ("model" in msg.lower() and ("not found" in msg.lower() or "does not exist" in msg.lower())):
            return ModelUnavailableError()
        if code == 403:
            return ProviderError("AI provider rejected the request (403). Check permissions.", "provider")
        return ProviderError(f"OpenAI API error: {msg}", "provider")


def classify_provider_error(e: Exception) -> Tuple[str, str]:
    """Return (user_message, kind) for a raised provider exception."""
    if isinstance(e, ProviderError):
        return e.message, e.kind
    # Generic classification fallback
    msg = str(e).lower()
    if "401" in msg or "unauthorized" in msg or "authentication" in msg:
        return "AI provider authentication failed. Check your API key.", "authentication"
    if "402" in msg or "quota" in msg or "credit" in msg or "billing" in msg:
        return "AI provider quota/credits exhausted.", "quota"
    if "429" in msg or "rate" in msg:
        return "AI provider rate limit hit. Try again shortly.", "rate_limit"
    if "404" in msg or ("model" in msg and "not" in msg):
        return "AI model unavailable or not found.", "model_unavailable"
    return f"AI provider error: {str(e)}", "provider"


def create_ai_provider(provider_name: str, api_key: str, model: str, extra_key: str = "", extra_model: str = "", zen_key: str = "", zen_model: str = "", zen_base_url: str = "") -> AIProvider:
    """Factory. Falls back between providers when 'auto' is used."""
    name = (provider_name or "auto").lower()
    if name == "auto":
        if zen_key:
            return OpenCodeZenProvider(zen_key, zen_model or model, zen_base_url)
        if api_key:
            return AnthropicProvider(api_key, model)
        if extra_key:
            return OpenAIProvider(extra_key, extra_model or model or "gpt-4o")
        raise AuthenticationError(
            "No AI API key configured. Set OPENCODE_ZEN_API_KEY, AI_API_KEY or "
            "OPENAI_API_KEY in your .env or Streamlit secrets."
        )
    if name == "opencode_zen":
        key = api_key or extra_key or zen_key
        chosen_model = zen_model or extra_model or model or OpenCodeZenProvider.DEFAULT_MODEL
        return OpenCodeZenProvider(key, chosen_model, zen_base_url)
    if name == "anthropic":
        key = api_key or extra_key
        return AnthropicProvider(key, model)
    if name == "openai":
        key = api_key or extra_key
        # Use the OpenAI-specific model when provided; fall back to the generic
        # model only if the OpenAI one is empty. This honors OPENAI_MODEL from .env.
        return OpenAIProvider(key, extra_model or model or "gpt-4o")
    raise ProviderError(f"Unknown AI provider: {provider_name}")
