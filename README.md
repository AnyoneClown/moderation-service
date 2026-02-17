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
# Edit .env with your OpenAI and HuggingFace API keys

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
│       ├── openai_service.py   # OpenAI Moderation API client
│       ├── hf_service.py       # HuggingFace Inference API client
│       ├── profanity_service.py # Local better-profanity filter
│       └── aggregator.py       # Scoring + decision engine
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
| OpenAI Moderation | 0.45 | Hate, violence, self-harm, sexual content |
| HuggingFace Spam | 0.30 | BERT-tiny spam classifier |
| Profanity Filter | 0.25 | Local swear-word detection |

| Score Range | Status |
|---|---|
| < 0.30 | ✅ APPROVED |
| 0.30 – 0.64 | ⚠️ FLAGGED |
| ≥ 0.65 | ❌ REJECTED |

If an external API is unavailable, weights are redistributed among available sources and the result is marked as **Partial**.

## API Keys

- **OpenAI**: Get a free key at https://platform.openai.com/api-keys (the `/v1/moderations` endpoint is free).
- **HuggingFace**: Get a token at https://huggingface.co/settings/tokens (free Inference API for public models).

## Tech Stack

- **Backend**: FastAPI, Python 3.11, async/await
- **Database**: PostgreSQL 16, SQLAlchemy 2.0 (async)
- **AI Services**: OpenAI Moderation API, HuggingFace Inference API, better-profanity
- **Frontend**: Jinja2 + Tailwind CSS (CDN)
- **DevOps**: Docker multi-stage build, Docker Compose with healthchecks
