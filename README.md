# 🩺 Code Doctor AI

An AI-powered **GitHub repository debugging assistant**. Paste a GitHub repo URL and Code Doctor fetches the code, scans it for security weaknesses and dependency risks, analyzes it, generates targeted fixes, runs your test suite, verifies the fixes, and produces a professional report — all from a cinematic dark/gold dashboard.

## ✨ Features

- 🐙 **GitHub Repository Ingestion** — paste a repo URL, Code Doctor fetches (zip-based, no git clone), respects ignore rules and size limits, and analyzes every supported file.
- 🔍 **Multi-Language Parsing** — Python (AST), JavaScript/TypeScript (regex), Java, C/C++, Go, Rust, PHP, Ruby, SQL, HTML/CSS, manifests and more.
- 🔒 **Security Scanning** — 20+ patterns: hardcoded secrets (always **masked**), eval/exec, unsafe deserialization, SQL injection, XSS, path traversal, shell usage. Secret values never leak into evidence or reports.
- 📦 **Dependency Scanning** — parses `requirements.txt`, `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`; flags unpinned, EOL, and non-reproducible references (no fabricated CVEs).
- 🤖 **AI Analysis** — optional AI analysis for deep issue understanding and fix generation using **Google Gemini** by default (`gemini-3.5-flash-lite`), with Anthropic or OpenAI as alternatives.
- 🔧 **Automatic Fixes** — deterministic secret→env-variable replacement first, AI-driven fallback, with backup files and syntax validation.
- 🧪 **Test Generation & Execution** — generates tests and runs them safely in a subprocess with timeout (pytest/jest/vitest/mocha/go/cargo/junit/phpunit).
- ✅ **Fix Verification** — PASS / FAIL / BLOCKED / NOT_VERIFIED outcomes based on syntax checks and test runs.
- 📊 **Detailed Reports** — professional Markdown and JSON reports with a health score (0-100), downloadable.
- 🎨 **Cinematic UI** — dark/gold theme, animated rain canvas, and a clickable Code Doctor buddy with cursor-following eyes.

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (developed and tested against 3.14)
- API key from [Google AI Studio](https://aistudio.google.com/apikey) *(free — recommended)*, or [Anthropic](https://console.anthropic.com/) / [OpenAI](https://platform.openai.com/) *(optional — the app degrades gracefully to static/security/dependency scanning without one)*

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd CODE-DOCTOR-AI-USED-TO-CORRECT-THE-GIT-HUB-REPO
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure API keys** (optional)

Create a `.env` file in the project root (see `.env.example`):
```env
# Default: Google Gemini (gemini-3.5-flash-lite) — get a key at https://aistudio.google.com/apikey
AI_PROVIDER=gemini
GEMINI_API_KEY=your_google_gemini_api_key_here
# GEMINI_MODEL=gemini-3.5-flash-lite

# Or for Anthropic
# AI_PROVIDER=anthropic
# AI_API_KEY=your_anthropic_api_key_here

# Or for OpenAI
# AI_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key_here
```

4. **Run the application**
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## ☁️ Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud) → **New app**, select the repo, set **Main file path** to `app.py`, and click **Deploy**.
3. Configure your AI provider secrets in **Settings → Secrets** (the app reads these automatically):

```toml
# Example secrets (replace with your real keys)
AI_PROVIDER = "gemini"      # "gemini", "anthropic", "openai", or "auto"

# Default: Google Gemini (gemini-3.5-flash-lite) — get a key at https://aistudio.google.com/apikey
GEMINI_API_KEY = "AIza-..."
# GEMINI_MODEL = "gemini-3.5-flash-lite"

# Use these keys instead if you prefer the paid providers:
# AI_API_KEY = "sk-ant-..."            # Anthropic
# OPENAI_API_KEY = "sk-..."            # OpenAI
# AI_MODEL = "claude-sonnet-4-20250514"
# OPENAI_MODEL = "gpt-4o"
```

> Only add **one** provider's key (or use `AI_PROVIDER = "auto"`). With no key the
> app still runs static/security/dependency scans. Without an AI key it falls back
> gracefully rather than failing.

## 📖 Usage

1. **Enter a GitHub repository URL** (e.g. `https://github.com/octocat/Hello-World`) and click **Start Analysis**.
2. **Scanning** — watch live progress as the repo is fetched, parsed, and analyzed across static, security, dependency and AI passes.
3. **Dashboard** — health score, file/language stats, and issue severity breakdown.
4. **Issues** — filter by severity/category, inspect each issue's evidence, and apply (or revert) fixes.
5. **Tests** — generate and run tests, then see the pass/fail summary.
6. **Report** — download the full Markdown or JSON analysis report.

## 🛠️ Configuration

Edit `config.py` or use environment variables:

```python
# AI Provider Settings
AI_PROVIDER=gemini        # 'gemini', 'anthropic', 'openai', or 'auto'
GEMINI_MODEL=gemini-3.5-flash-lite   # default model
# AI_MODEL=claude-sonnet-4-20250514
# OPENAI_MODEL=gpt-4o

# Application Settings
MAX_FILE_SIZE_MB=10
ENABLE_SECURITY_SCAN=true
ENABLE_TEST_GENERATION=true
ENABLE_AI_ANALYSIS=true

# Repository scanning limits
MAX_REPOSITORY_MB=200
MAX_FILES=3000
GITHUB_REQUEST_TIMEOUT=30
TEST_TIMEOUT_SECONDS=180
```

## 📋 Supported Languages

Python (.py), JavaScript (.js/.jsx/.mjs/.cjs), TypeScript (.ts/.tsx), Java (.java), C/C++ (.c/.h/.cpp/.hpp/.cc/.cxx), C# (.cs), Go (.go), Rust (.rs), PHP (.php), Ruby (.rb), Swift (.swift), Kotlin (.kt/.kts), HTML, CSS, SQL, Shell, JSON, YAML, TOML, XML, Markdown, Dockerfile, Makefile.

## 📦 Architecture

```
app.py                 Streamlit entrypoint (stages: landing → scanning → dashboard → issues → tests → report)
config.py              Central configuration & limits
core/
  repository.py        GitHub URL parsing, zip fetching, path safety, temp workspace
  code_parser.py       File discovery + language parsing (AST/regex)
  security_scanner.py  Security & secret scanning (masked output)
  dependency_scanner.py Manifest parsing
  analyzer.py          Orchestrates the full analysis pipeline
  ai_provider.py       Gemini / Anthropic / OpenAI adapters + error classification
  fixer.py             Deterministic + AI fixes with backups
  test_generator.py    Test generation
  test_runner.py       Safe subprocess test execution
  verifier.py          Fix verification (PASS/FAIL/BLOCKED/NOT_VERIFIED)
  reporter.py          Health score + Markdown/JSON reports
ui/
  theme.py             Dark/gold CSS + rain/buddy JS
  components.py        Reusable UI components
tests/                 pytest suite
```

## 🔍 Issue Severity Levels

- 🔴 **CRITICAL** — must fix immediately (security risks, crashes)
- 🟠 **HIGH** — significant issues requiring attention
- 🟡 **MEDIUM** — potential problems to review
- 🔵 **LOW / INFO** — code quality improvements and context notes

## 🔒 Security

- Detected secret values are **always masked** (`'********'`) in evidence, fixes, and reports — raw secrets never leak.
- Repositories are analyzed locally first; code is only sent to an AI provider if you configure an API key.
- Test execution uses a known-safe command allowlist and a hard timeout.
- No fabricated CVEs: dependency scanning flags structural risks (unpinned / EOL / non-reproducible) rather than inventing version-specific advisories.
- Repository scans intentionally downgrade "dangerous pattern used inside a `pytest.raises` block" from HIGH to INFO to avoid false positives.

## ✅ Testing

```bash
python -m pytest -q
```

The suite covers repository parsing, security/dependency scanning, secret masking, deterministic fixes, validators, report generation, health scoring, test-runner detection, and verification.

## 🤝 Contributing

Contributions are welcome. Please open an issue or pull request.

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.

---

**Made with ❤️ by developers, for developers**
