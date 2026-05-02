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

## Supabase Instead of Local Postgres

The app already uses plain PostgreSQL via SQLAlchemy and `asyncpg`, so you can
swap the database backend to Supabase without rewriting the data layer.

1. Create a Supabase project.
2. In the Supabase dashboard, copy either:
   - the **Direct connection string** for a persistent server with IPv6 support, or
   - the **Session pooler** connection string for general deployment platforms.
3. Set these values in `.env`:

```env
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
DATABASE_SSL_MODE=require
```

The app normalizes Supabase `postgresql://` URLs to the `asyncpg` SQLAlchemy
driver automatically. By default, `docker compose up --build` starts only the
web app, which is what you want when using Supabase.

`DATABASE_SSL_MODE=require` enables TLS without certificate verification, which
is often the most practical setting for managed pooler endpoints. If you want
strict certificate validation, switch to `DATABASE_SSL_MODE=verify-full`.

If you want the bundled local PostgreSQL container instead, run:

```bash
docker compose --profile localdb up --build
```

## Deploy on Render

This repo is ready for a Docker-based Render web service.

1. Push the repo to GitHub.
2. In Render, create a new **Web Service** from that GitHub repo.
3. Render should detect the included `render.yaml`, or you can configure the service manually as:
   - **Runtime**: Docker
   - **Health check path**: `/health`
4. Add these environment variables in Render:
   - `DATABASE_URL` = your Supabase connection string
   - `DATABASE_SSL_MODE` = `require`
   - `DATABASE_POOL_PRE_PING` = `true`
   - `HF_API_TOKEN` = your Hugging Face token
   - `NVIDIA_API_KEY` = your NVIDIA API key
5. Deploy.

Render provides the runtime `PORT` environment variable automatically for web
services, and the container is configured to bind to it.

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
