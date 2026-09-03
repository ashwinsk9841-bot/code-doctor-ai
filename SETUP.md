# Setup Guide - Code Doctor AI

## Prerequisites

- **Python 3.10 or higher** (developed and tested against 3.14)
- **pip** (Python package manager)
- **API Key** (optional) from either:
  - [Anthropic Console](https://console.anthropic.com/) (recommended)
  - [OpenAI Platform](https://platform.openai.com/)

> Without an API key the app still works — it performs static, security, and
> dependency scanning and skips AI-powered analysis/fixes gracefully.

## Installation Steps

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Edit `.env` and add your API key:

**For Anthropic (Claude):**
```env
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-your-key-here
AI_MODEL=claude-sonnet-4-20250514
```

**For OpenAI (GPT):**
```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4-turbo-preview
```

### 3. Run the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

### 4. Analyze a Repository

In the app, paste a **GitHub repository URL** (e.g. `https://github.com/octocat/Hello-World`)
and click **Start Analysis**. Code Doctor fetches the repo (zip-based, no git clone),
runs the scanning pipeline, then lets you inspect issues, apply fixes, run tests, and
download a report.

## Configuration Options

Edit `config.py` or add to `.env`:

```env
# File size limit (MB)
MAX_FILE_SIZE_MB=10

# Feature toggles
ENABLE_SECURITY_SCAN=true
ENABLE_TEST_GENERATION=true
ENABLE_AI_ANALYSIS=true

# Repository scanning limits
MAX_REPOSITORY_MB=200
MAX_FILES=3000
GITHUB_REQUEST_TIMEOUT=30
TEST_TIMEOUT_SECONDS=180
```

## Troubleshooting

### "No AI analysis is happening" (no error)

This is expected when no API key is configured. The app runs static, security, and
dependency scans. To enable AI analysis/fixes, create a `.env` file with a valid key
and restart the app.

### "Repository could not be loaded"

- Make sure the URL is a public GitHub repository URL (`https://github.com/<owner>/<repo>`).
- URLs pointing at a specific file or `/blob/...` path, or to a private repo without
  access, will fail. Check the displayed error message in the app.

### Import Errors

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Port Already in Use

```bash
# Run on a different port
streamlit run app.py --server.port 8502
```

## Development Setup

### Install Development Tools

```bash
pip install pytest black flake8 pylint
```

### Run Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black . --line-length 100
```

### Linting

```bash
flake8 . --max-line-length 100
pylint core/ utils/
```

## Project Structure

```
CODE-DOCTOR-AI/
├── app.py                  # Main Streamlit application
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── .env.example           # Example environment file
├── core/                   # Core modules
│   ├── ai_provider.py     # AI provider interface (Anthropic/OpenAI)
│   ├── analyzer.py        # Analysis pipeline orchestrator
│   ├── code_parser.py     # File discovery + language parsing
│   ├── dependency_scanner.py # Manifest/package scanning
│   ├── fixer.py           # Code fixing logic
│   ├── repository.py      # GitHub ingestion, path safety
│   ├── reporter.py        # Health score + Markdown/JSON reports
│   ├── security_scanner.py # Security & secret scanner
│   ├── test_generator.py  # Test generation
│   ├── test_runner.py     # Safe test execution
│   └── verifier.py        # Fix verification
├── utils/                  # Utility modules
│   ├── file_handler.py    # File operations
│   ├── language_detector.py # Language detection
│   └── validators.py      # Input validation
├── tests/                  # Test files
└── ui/                     # Theme + reusable UI components
```

## API Key Setup

### Getting an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Copy and add to `.env`

### Getting an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Copy and add to `.env`

## Deploying to Streamlit Community Cloud

1. **Push this repository to GitHub.**
2. **Create the app** — go to [Streamlit Community Cloud](https://streamlit.io/cloud),
   click **New app**, connect your GitHub account, select the repo, set
   **Main file path** to `app.py`, and click **Deploy**.
3. **Add secrets** — after deployment, open the app's **Settings → Secrets**
   and paste TOML with your provider key:

```toml
# Anthropic provider (either use this, or the OpenAI block below)
AI_PROVIDER = "anthropic"
AI_API_KEY = "sk-ant-your-key-here"
AI_MODEL = "claude-sonnet-4-20250514"
```

```toml
# OpenAI provider (alternative)
AI_PROVIDER = "openai"
OPENAI_API_KEY = "sk-your-openai-key-here"
OPENAI_MODEL = "gpt-4o"
```

> **Only one provider key is required.** If you set both keys, set
> `AI_PROVIDER = "auto"` to let the app pick. The app reads these secrets on
> startup via `Config.load_from_secrets()`. Without any key, the deployed app
> still runs static/security/dependency scans.

## Next Steps

1. **Test the application** - Run `streamlit run app.py` and analyze a GitHub repo
2. **Customize settings** - Adjust `config.py` for your needs
3. **Add languages** - Extend `SUPPORTED_LANGUAGES` if needed
4. **Enable AI** - Add an API key to `.env` for AI-powered analysis and fixes

## Support

For issues or questions:
- Check the [README.md](README.md)
- Review [Troubleshooting](#troubleshooting) above
- Open an issue on GitHub

---

**Ready to analyze code!** Run `streamlit run app.py` to get started.
