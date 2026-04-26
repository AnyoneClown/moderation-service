# Automated Intelligent Content Moderation System

A production-ready web application that detects **spam**, **toxicity**, and **prohibited language** in social-media posts using pre-trained AI models and free APIs.

## Architecture

```
┌──────────────┐       ┌──────────────────────────────────────────┐
│   Browser    │──────▶│  FastAPI (Jinja2 SSR + Tailwind CSS)     │
│  (Dashboard) │◁──────│                                          │
└──────────────┘       │  ┌────────────────────────────────────┐  │
                       │  │       Aggregator (scoring engine)   │  │
                       │  │  asyncio.gather ──────────────────▶ │  │
                       │  │  ┌──────────┬───────────┬────────┐ │  │
                       │  │  │ OpenAI   │ HuggingFace│ Local  │ │  │
                       │  │  │ Moder.   │ Spam Det.  │ Filter │ │  │
                       │  │  └──────────┴───────────┴────────┘ │  │
                       │  └────────────────────────────────────┘  │
                       │           │                               │
                       │           ▼                               │
                       │    PostgreSQL (history log)               │
                       └──────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env with your NVIDIA NIM and HuggingFace API keys

# 2. Launch with Docker Compose
docker compose up --build

# 3. Open in browser
open http://localhost:8000
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app, routes, lifespan
│   ├── config.py            # Pydantic settings from .env
│   ├── database.py          # Async SQLAlchemy engine & session
│   ├── schemas.py           # Pydantic request/response models
│   ├── models/
│   │   └── moderation.py    # ModerationRecord ORM model
│   └── services/
│       ├── hf_service.py          # HuggingFace spam classifier
│       ├── hf_toxicity_service.py # HuggingFace toxicity classifier
│       ├── hf_xray_service.py     # NVIDIA NIM X-Ray highlighter
│       ├── nvidia_nim_service.py  # Shared NVIDIA NIM client
│       ├── profanity_service.py   # NVIDIA NIM profanity classifier
│       └── aggregator.py          # Scoring + decision engine
├── templates/               # Jinja2 HTML templates (Tailwind CDN)
│   ├── base.html
│   ├── dashboard.html
│   ├── result.html
│   ├── history.html
│   └── error.html
├── static/                  # Static assets (if any)
├── Dockerfile               # Multi-stage optimised build
├── docker-compose.yml       # web + db orchestration
├── requirements.txt
├── .env.example
└── README.md
```

## Scoring System

| Source | Weight | Description |
|---|---|---|
| HuggingFace Toxicity | 0.25 | Toxicity and hate-speech detection |
| HuggingFace Spam | 0.20 | BERT-tiny spam classifier |
| Profanity Filter | 0.20 | NVIDIA NIM profanity and toxic-language detection |
| Fraud Detector | 0.25 | Scam, phishing, and fraud indicators |
| Sentiment | 0.10 | Negative sentiment signal |

| Score Range | Status |
|---|---|
| < 0.25 | ✅ APPROVED |
| 0.25 – 0.54 | ⚠️ FLAGGED |
| ≥ 0.55 | ❌ REJECTED |

If an external API is unavailable, weights are redistributed among available sources and the result is marked as **Partial**.

## API Keys

- **NVIDIA NIM**: Set `NVIDIA_API_KEY` for `https://integrate.api.nvidia.com/v1`.
- **HuggingFace**: Get a token at https://huggingface.co/settings/tokens (free Inference API for public models).

## Tech Stack

- **Backend**: FastAPI, Python 3.11, async/await
- **Database**: PostgreSQL 16, SQLAlchemy 2.0 (async)
- **AI Services**: NVIDIA NIM, HuggingFace Inference API
- **Frontend**: Jinja2 + Tailwind CSS (CDN)
- **DevOps**: Docker multi-stage build, Docker Compose with healthchecks
