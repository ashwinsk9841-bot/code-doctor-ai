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
import time
from typing import Dict, Any, Optional, List, Tuple, Callable
from abc import ABC, abstractmethod

from config import Config


def _retry_with_backoff(fn: Callable[[], Any], classify: Callable[[Exception], Exception],
                        max_attempts: Optional[int] = None,
                        initial_delay: Optional[float] = None,
                        backoff: Optional[float] = None) -> Any:
    """Call ``fn`` retrying with exponential backoff on rate-limit errors.

    The raw SDK call may raise 429 / rate-limit errors (which are classified as
    :class:`RateLimitedError`). We retry a bounded number of times with a sleep
    between attempts so transient provider pressure doesn't immediately fail the
    request — while never looping aggressively or hammering the endpoint.
    ``max_attempts`` here means the total number of tries (including the first).

    If the provider includes a ``Retry-After`` header on the 429, we honour that
    exact delay instead of the default backoff. Other error kinds are classified
    and raised immediately.
    """
    attempts = max_attempts if max_attempts is not None else Config.AI_RETRY_MAX
    delay = initial_delay if initial_delay is not None else Config.AI_RETRY_INITIAL_DELAY
    factor = backoff if backoff is not None else Config.AI_RETRY_BACKOFF
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            err = classify(e)
            if isinstance(err, RateLimitedError) and attempt < attempts - 1:
                wait = err.retry_after if getattr(err, "retry_after", None) else delay
                time.sleep(max(0.0, wait))
                delay = max(wait, delay * max(1.0, factor))
                continue
            raise err
    raise _unreachable_rate_limit()


def _unreachable_rate_limit() -> "RateLimitedError":
    """Fallback guard so the retry helper always raises on exhaustion."""
    return RateLimitedError()


def _retry_after_seconds(e: Exception) -> Optional[float]:
    """Read a ``Retry-After`` header/value from a 429 exception, if present.

    Some SDK errors expose response headers on ``e.response`` (openai) or
    ``e.headers`` / ``e.response.headers`` (anthropic). ``Retry-After`` may be
    an integer number of seconds or an HTTP-date; we only handle the numeric
    form (the common case) and cap it to avoid sleeping too long.
    """
    import email.utils
    headers = None
    for attr in ("headers",):
        probe = getattr(e, attr, None)
        if probe:
            headers = probe
            break
    if headers is None:
        resp = getattr(e, "response", None)
        headers = getattr(resp, "headers", None)
    if not headers:
        return None
    raw = None
    if hasattr(headers, "get"):
        raw = headers.get("retry-after")
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw.isdigit():
        return min(max(0.0, float(raw)), 60.0)
    try:
        parsed = email.utils.parsedate(raw)
        if parsed:
            from datetime import datetime
            delay = datetime(*parsed[:6]).timestamp() - time.time()
            return min(max(0.0, delay), 60.0)
    except Exception:
        return None
    return None


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
    def __init__(self, message="AI provider rate limit hit. Try again shortly.", retry_after: Optional[float] = None):
        self.retry_after = retry_after
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

    def analyze_many(self, files: List[Dict[str, Any]], max_chars_per_file: int = 4000) -> Dict[str, Any]:
        """Analyze several files in a SINGLE AI request, attributing each issue to its file.

        Returns a dict like ``{"issues": [...], "overall_quality": "..."}`` where every
        issue carries a ``"file"`` key matching the path of the file it belongs to.
        Files are capped per-file to bound token usage. Issues whose ``file`` is missing
        default to the final fallback file.
        """
        if not files:
            return {"issues": [], "overall_quality": "UNKNOWN"}

        blocks = []
        for record in files:
            path = record.get("path", "<unknown>")
            content = (record.get("content") or "")[:max_chars_per_file]
            blocks.append(f"### FILE: {path}\n```\n{content}\n```")
        combined = "\n\n".join(blocks)

        system = (
            "You are Code Doctor AI, a senior code reviewer. Analyze ALL of the files "
            "provided below. Return ONLY a valid JSON object. Do not include markdown, "
            "code fences, or prose outside the JSON.\n\n"
            'Schema: {"issues": [{"file": str, "title": str, "category": one of '
            'BUG,SECURITY,DEPENDENCY,PERFORMANCE,CODE_QUALITY,CONFIGURATION,TEST,OTHER, '
            '"severity": one of CRITICAL,HIGH,MEDIUM,LOW,INFO, '
            '"line": int|null, "line_end": int|null, '
            '"description": str, "why_it_matters": str, "evidence": str, '
            '"recommended_fix": str, "fixable": bool, "confidence": number 0..1}], '
            '"overall_quality": "CRITICAL|POOR|FAIR|GOOD|EXCELLENT"} '
            'The "file" field of each issue MUST match one of the "### FILE:" paths above. '
            "Only report genuine, code-grounded issues with high confidence. "
            "Do not invent vulnerabilities that are not present."
        )
        user_message = f"Analyze the following source files:\n\n{combined}"
        raw = self.complete(system, user_message, max_tokens=6000)
        data = self._extract_json(raw, default={"issues": [], "overall_quality": "UNKNOWN"})

        known = {f.get("path") for f in files}
        fallback = files[-1].get("path")
        issues = []
        for iss in data.get("issues", []):
            fpath = iss.get("file")
            # Only trust file paths that were actually provided to the model;
            # otherwise attribute to the last (fallback) file to avoid invented paths.
            if fpath not in known or not fpath:
                fpath = fallback
            iss["file"] = fpath
            issues.append(iss)
        return {"issues": issues, "overall_quality": data.get("overall_quality", "UNKNOWN")}

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
        self.timeout = Config.AI_REQUEST_TIMEOUT
        try:
            import anthropic
        except ImportError:
            raise ProviderError(
                "The 'anthropic' package is not installed. Run: pip install anthropic",
                "dependency",
            )
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=self.timeout)

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        def _call():
            return self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        try:
            response = _retry_with_backoff(_call, self._classify)
            return response.content[0].text
        except RateLimitedError:
            raise
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
            return RateLimitedError(retry_after=_retry_after_seconds(e))
        if "not_found" in msg.lower() or ("model" in msg.lower() and "not" in msg.lower()):
            return ModelUnavailableError()
        return ProviderError(f"Anthropic API error: {msg}", "provider")


class GeminiProvider(AIProvider):
    """Google Gemini provider using the ``google-generativeai`` SDK.

    Uses the stable ``gemini-3.5-flash-lite`` model for fast code analysis
    and fixes. System instructions are passed via ``system_instruction`` and
    the ``max_tokens`` parameter maps to ``max_output_tokens``.
    """

    provider_name = "gemini"
    DEFAULT_MODEL = "gemini-3.5-flash-lite"

    def __init__(self, api_key: str, model: str = "", timeout: Optional[float] = None):
        if not api_key:
            raise AuthenticationError("Google Gemini API key is required.")
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout if timeout is not None else Config.AI_REQUEST_TIMEOUT
        try:
            import google.generativeai as genai
        except ImportError:
            raise ProviderError(
                "The 'google-generativeai' package is not installed. Run: pip install google-generativeai",
                "dependency",
            )
        self._genai = genai
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction="You are Code Doctor AI.",
        )

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        def _call():
            return self.client.generate_content(
                user_message,
                generation_config=self._genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.2,
                ),
                stream=False,
            )
        try:
            response = _retry_with_backoff(_call, self._classify)
            if response.text:
                return response.text
            return ""
        except RateLimitedError:
            raise
        except Exception as e:
            raise self._classify(e)

    @staticmethod
    def _classify(e: Exception) -> ProviderError:
        msg = str(e)
        code = getattr(getattr(e, "status_code", None), "code", None) or getattr(e, "status_code", None)
        if code == 400 and ("api key" in msg.lower() or "invalid" in msg.lower()):
            return AuthenticationError()
        if code == 401 or "api_key_invalid" in msg.lower() or "permission_denied" in msg.lower() or "unauthenticated" in msg.lower():
            return AuthenticationError()
        if code == 402 or "quota" in msg.lower() or "billing" in msg.lower() or "exceeded" in msg.lower():
            return QuotaExceededError()
        if code == 429 or "rate" in msg.lower() or "resource_exhausted" in msg.lower():
            return RateLimitedError(retry_after=_retry_after_seconds(e))
        if code == 404 or ("model" in msg.lower() and ("not found" in msg.lower() or "does not exist" in msg.lower())):
            return ModelUnavailableError()
        if code == 403:
            return ProviderError("Gemini API rejected the request (403). Check permissions.", "provider")
        return ProviderError(f"Gemini API error: {msg}", "provider")


class OpenAIProvider(AIProvider):
    """OpenAI provider."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str = ""):
        if not api_key:
            raise AuthenticationError("OpenAI API key is required.")
        self.api_key = api_key
        self.model = model or "gpt-4o"
        self.timeout = Config.AI_REQUEST_TIMEOUT
        try:
            import openai
        except ImportError:
            raise ProviderError(
                "The 'openai' package is not installed. Run: pip install openai",
                "dependency",
            )
        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key, timeout=self.timeout)

    def _normalize_model(self) -> str:
        return self.model

    def complete(self, system: str, user_message: str, max_tokens: int = 4000) -> str:
        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                timeout=self.timeout,
            )
        try:
            response = _retry_with_backoff(_call, self._classify)
            return response.choices[0].message.content
        except RateLimitedError:
            raise
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
            return RateLimitedError(retry_after=_retry_after_seconds(e))
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


def create_ai_provider(provider_name: str, api_key: str, model: str, extra_key: str = "", extra_model: str = "", gemini_key: str = "", gemini_model: str = "") -> AIProvider:
    """Factory. Falls back between providers when 'auto' is used."""
    name = (provider_name or "auto").lower()
    if name == "auto":
        if gemini_key:
            return GeminiProvider(gemini_key, gemini_model or model)
        if api_key:
            return AnthropicProvider(api_key, model)
        if extra_key:
            return OpenAIProvider(extra_key, extra_model or model or "gpt-4o")
        raise AuthenticationError(
            "No AI API key configured. Set GEMINI_API_KEY (recommended), "
            "AI_API_KEY or OPENAI_API_KEY in your .env or Streamlit secrets."
        )
    if name == "gemini":
        key = gemini_key or api_key or extra_key
        return GeminiProvider(key, gemini_model or model or GeminiProvider.DEFAULT_MODEL)
    if name == "anthropic":
        key = api_key or extra_key
        return AnthropicProvider(key, model)
    if name == "openai":
        key = api_key or extra_key
        return OpenAIProvider(key, extra_model or model or "gpt-4o")
    raise ProviderError(f"Unknown AI provider: {provider_name}")
