# Diploma Project: AI Content Moderation System

## 1. Project Overview

This is a comprehensive **AI-powered Content Moderation System** designed to analyze text and audio content for safety and compliance. It uses a **multi-modal, multi-engine architecture** to detect toxicity, spam, fraud, profanity, and negative sentiment.

The system aggregates results from **5 distinct analysis engines** to produce a final weighted safety score and a decision (APPROVED, FLAGGED, or REJECTED). Uniquely, it provides **"X-Ray" explainability**, highlighting exactly which parts of the content triggered specific detection rules.

---

## 2. Architecture

The project follows a **Modular Monolith** architecture wrapped in **Docker containers**.

### 2.1 Technology Stack
- **Backend Framework**: Python 3.12 + **FastAPI** (modern, async, high-performance).
- **Database**: **PostgreSQL 16** (accessed via `SQLAlchemy 2.0` in async mode).
- **External AI**: **Hugging Face Inference API** (for heavy transformer models).
- **Local AI/NLP**: `NLTK` (Sentiment), `better-profanity` (Profanity), `Regex` (Fraud).
- **Frontend**: **Jinja2** (Server-Side Rendering) + vanilla CSS (no complex JS build chain).
- **Infrastructure**: **Docker Compose** orchestrates the web app and database.

### 2.2 Container Structure
The system consists of two main services defined in `docker-compose.yml`:
1.  **`web`**: The main FastAPI application.
2.  **`db`**: The PostgreSQL database.

---

## 3. Core Principles

### 3.1 Defense in Depth (Hybrid Detection)
No single model is perfect. This system combines **Deterministic Rules** (Regex, Keyword blocklists) with **Probabilistic AI** (Transformer models, Sentiment analysis).
- If the AI misses a subtle scam, the Regex engine might catch it.
- If the Regex misses a new slang term, the Toxicity model might catch it.

### 3.2 Explainable AI (X-Ray)
A black-box "REJECTED" label is frustrating for users. This project implements an **"X-Ray" feature**:
- It maps detection results back to specific character spans in the original text.
- It generates an HTML representation where specific words are highlighted (e.g., Red for Profanity, Orange for Fraud).
- This is stored in the database (`xray_html` column) and displayed to the admin.

### 3.3 Fail-Safe Design
External APIs (like Hugging Face) can go down. The **Aggregator** is designed to be resilient:
- If an external service fails or times out, the system **redistributes the scoring weight** among the remaining active services.
- This ensures the system can still make a decision even in partial outage scenarios.

---

## 4. How It Works (The Pipeline)

When a user submits content to the `/moderate` endpoint, the following pipeline executes:

### Step 1: Input Processing
- **Text**: Cleaned and prepared.
- **Audio**: Uploaded files are converted to WAV and **transcribed** to text using a local speech-to-text service (or API) before analysis.

### Step 2: Parallel Analysis (The 5 Engines)
The `aggregator.py` service dispatches the text to 5 analyzers simultaneously using `asyncio`:

1.  **Toxicity Engine** (`hf_toxicity_service.py`):
    -   Uses a **Hugging Face** Transformer model to detect hate speech, insults, and threats.
    -   *Weight: 25%*
2.  **Spam Engine** (`hf_service.py`):
    -   Uses `mrm8488/bert-tiny-finetuned-sms-spam-detection` to identify spam patterns.
    -   *Weight: 20%*
3.  **Fraud Engine** (`fraud_service.py`):
    -   **Local Regex Engine**. Detects financial scams ("wire transfer", "crypto"), phishing ("verify account"), and urgency tactics ("act now").
    -   *Weight: 25%*
4.  **Profanity Engine** (`profanity_service.py`):
    -   Local keyword matching using `better-profanity` and custom English/Ukrainian blocklists.
    -   *Weight: 20%*
5.  **Sentiment Engine** (`sentiment_service.py`):
    -   Uses **NLTK VADER** to detect overwhelmingly negative emotional tone.
    -   *Weight: 10%*

### Step 3: Aggregation & Scoring
The **Aggregator** combines these inputs:

$$ \text{Final Score} = \sum (\text{Service Score} \times \text{bService Weight}) $$

**Decision Logic:**
- **APPROVED**: Score < 0.25
- **FLAGGED**: Score 0.25 - 0.55
- **REJECTED**: Score > 0.55

**Critical Overrides**:
Even if the average is low, if **ANY** single critical source (like Fraud) returns a score > 0.75, the content is automatically **REJECTED** to prevent dangerous content from slipping through.

### Step 4: Storage & Reporting
1.  **Persistence**: The result is saved to PostgreSQL (`ModerationRecord` model) using UUIDs.
2.  **Reporting**: A PDF report can be generated (`pdf_service.py`) summarizing the findings for compliance records.

---

## 5. Key File Structure

| File Path | Description |
| :--- | :--- |
| `app/main.py` | Entry point. Configures routes, DB connection, and templates. |
| `app/services/aggregator.py` | **The Brain.** Orchestrates the 5 services and calculates final weight. |
| `app/services/fraud_service.py` | **Local Logic.** Complex Regex patterns for scam detection. |
| `app/models/moderation.py` | **Data Model.** Defines the SQL schema, including JSON fields for detailed logs. |
| `app/services/hf_service.py` | **External API.** Client for Hugging Face Inference. |
| `docker-compose.yml` | **Infrastructure.** Defines how the App and Database talk to each other. |

---

## 6. How to Run

1.  **Configure Environment**:
    Create a `.env` file with your credentials (database URL, Hugging Face Token).
2.  **Start Services**:
    ```bash
    docker-compose up --build
    ```
3.  **Access Application**:
    -   Dashboard: `http://localhost:8000`
    -   API Docs: `http://localhost:8000/docs`
