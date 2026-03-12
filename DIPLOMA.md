# Diploma Project: AI-Powered Multi-Modal Content Moderation System

*(Scroll down for the Ukrainian version | Українська версія нижче)*

---

## 🇬🇧 ENGLISH VERSION

### 1. Abstract / Project Overview
The project is an AI-powered, multi-modal content moderation application capable of analyzing and filtering various forms of digital content (text, audio, images). The system is designed to automatically detect toxic language, profanity, fraud attempts, sensitive personal data (PII), and inappropriate imagery (e.g., adult content or X-ray image analysis, depending on the specific model used). It provides an interactive web dashboard for real-time content submission and review, alongside a history of past moderations and downloadable PDF reports.

### 2. Main Goal and Concept
The primary goal of the project is to automate the moderation process in digital environments (like forums, social networks, or customer support chats) by leveraging modern Machine Learning (ML) APIs and Natural Language Processing (NLP) techniques. 
Instead of relying solely on manual review or simple keyword blocking, the system aggregates multiple specialized ML services to evaluate content comprehensively. The architecture is asynchronous and modular, making it highly scalable and adaptable to different business needs.

### 3. Technology Stack & Architecture
- **Backend Framework:** FastAPI (Python) - chosen for its high performance, asynchronous capabilities, and automatic OpenAPI documentation.
- **Database:** SQLite / PostgreSQL (via SQLAlchemy & asyncpg/aiosqlite) - used for persisting moderation history and results.
- **Frontend / UI:** HTML/CSS with Jinja2 Templates - serves a dynamic, multi-lingual web interface without the overhead of a heavy frontend framework.
- **Machine Learning & NLP Services:**
  - Hugging Face Inference API (Toxicity, Image Classification)
  - NLTK (VADER) for Sentiment Analysis
  - Presidio (Microsoft) / Custom logic for PII (Personally Identifiable Information) and Fraud detection.
  - SpeechRecognition / Audio Processing for audio file transcription.
- **Containerization:** Docker & Docker Compose - ensures isolated and reproducible environments for deployment.
- **Other utilities:** PDF generation (`reportlab` / `fpdf` or similar) for exporting results.

### 4. Core Features
- **Multi-Modal Input:** Accepts pure text, image files, and audio files.
- **Audio Transcription:** Converts spoken audio into text before running it through the text-based moderation pipeline.
- **Aggregated Moderation Pipeline:** 
  - **Toxicity Analysis:** Detects hate speech, insults, and threats.
  - **Profanity Filter:** Checks for banned words.
  - **Fraud Detection:** Identifies phishing or scam patterns.
  - **Sentiment Analysis:** Determines if the tone is positive, negative, or neutral.
  - **Image Analysis:** Uses ML to classify uploaded images.
- **Internationalization (i18n):** User interface is available in multiple languages (English and Ukrainian) using cookies and translation dictionaries.
- **Detailed Reporting:** Generates a unique moderation ID for every request, stores the detailed JSON results, and allows exporting the report to a PDF file.
- **History Dashboard:** A retrospective view of all analyzed content with aggregate scoring.

### 5. Project Structure & Logic
```text
diploma-project/
├── app/
│   ├── __init__.py
│   ├── config.py           # Environment variables and app configuration
│   ├── database.py         # Async SQLAlchemy engine and session management
│   ├── i18n.py             # Internationalization (English/Ukrainian translations)
│   ├── main.py             # FastAPI entry point, lifespan events, and HTTP routes
│   ├── schemas.py          # Pydantic models for request/response validation
│   ├── models/
│   │   └── moderation.py   # SQLAlchemy ORM models (e.g., ModerationRecord)
│   └── services/           # Business logic layer
│       ├── aggregator.py       # Orchestrator: calls multiple services and calculates a final risk score
│       ├── audio_service.py    # Handles audio file validation and speech-to-text
│       ├── fraud_service.py    # Scans text for fraud/scam indicators
│       ├── hf_service.py       # Base Hugging Face API integration
│       ├── hf_toxicity.py      # Specific Hugging Face model for toxicity
│       ├── hf_xray_service.py  # Specific Hugging Face model for image analysis
│       ├── pdf_service.py      # PDF report generation logic
│       ├── profanity_service.py# Checks text against a list of blocked words
│       └── sentiment_service.py# NLTK VADER sentiment analysis
├── static/
│   └── style.css           # UI styling
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Main layout, navbar, language switcher
│   ├── dashboard.html      # Content submission form
│   ├── error.html          # Error handling UI
│   ├── history.html        # Table view of past moderations
│   └── result.html         # Detailed view of a single moderation result
├── Dockerfile              # Instructions to build the application container
├── docker-compose.yml      # Multi-container orchestration (App + DB)
├── requirements.txt        # Python dependencies
└── README.md               # Quickstart guide
```

### 6. Data Flow / Business Logic
1. **User Input:** A user submits text, an image, or an audio file via the UI (`/` dashboard).
2. **Preprocessing (if applicable):** If audio is uploaded, `audio_service` transcribes it to text.
3. **Aggregation (`aggregator.py`):** The system passes the payload to the aggregator. 
   - Text is sent in parallel (or sequentially) to Sentiment, Toxicity, Fraud, and Profanity services.
   - Images are sent to `hf_xray_service.py` to be classified.
4. **Decision Making:** Each service returns localized scores and flags. The aggregator calculates a `Final Status` (e.g., APPROVED, FLAGGED, BLOCKED) based on weighted risk scores.
5. **Database Storage:** The complete input, individual service outputs, and the final decision are saved into the database using `ModerationRecord` via SQLAlchemy.
6. **Output:** The user is redirected to `/result/{id}` where they can view the breakdown of the analysis or download a PDF report via `/result/{id}/pdf`.

---

## 🇺🇦 УКРАЇНСЬКА ВЕРСІЯ

### 1. Анотація / Огляд проекту
Проект являє собою мультимодальну систему модерації контенту на базі штучного інтелекту, здатну аналізувати та фільтрувати різні форми цифрового контенту (текст, аудіо, зображення). Система розроблена для автоматичного виявлення токсичної лексики, ненормативної лексики, спроб шахрайства та неприйнятних зображень. Вона надає інтерактивну веб-панель для завантаження контенту в реальному часі, а також історію попередніх модерацій та можливість завантаження звітів у форматі PDF.

### 2. Головна мета та концепція
Основна мета проекту — автоматизація процесу модерації в цифровому середовищі (наприклад, на форумах, у соціальних мережах або чатах підтримки) з використанням сучасних API машинного навчання (ML) та методів обробки природної мови (NLP).
Замість того, щоб покладатися виключно на ручну перевірку або просте блокування за ключовими словами, система агрегує декілька спеціалізованих сервісів для комплексної оцінки контенту. Архітектура є асинхронною та модульною, що робить її легко масштабованою та адаптивною до різних бізнес-потреб.

### 3. Технологічний стек та архітектура
- **Бекенд-фреймворк:** FastAPI (Python) - обраний завдяки високій продуктивності, асинхронності та автоматичній документації OpenAPI.
- **База даних:** SQLite / PostgreSQL (через SQLAlchemy та asyncpg/aiosqlite) - використовується для збереження історії модерації та результатів.
- **Фронтенд / UI:** HTML/CSS з шаблонами Jinja2 - забезпечує динамічний, багатомовний веб-інтерфейс без необхідності використання важких фронтенд-фреймворків.
- **Сервіси машинного навчання (ML) та NLP:**
  - Hugging Face Inference API (токсичність, класифікація зображень).
  - NLTK (VADER) для аналізу тональності (Sentiment Analysis).
  - Спеціальна логіка для виявлення шахрайства (Fraud detection) та ненормативної лексики.
  - Розпізнавання мовлення (Speech-to-Text) для транскрибування аудіофайлів.
- **Контейнеризація:** Docker та Docker Compose - забезпечує ізольоване та відтворюване середовище для розгортання.
- **Інші утиліти:** Генерація PDF звітів для експорту результатів модерації.

### 4. Основні функції
- **Мультимодальне введення:** Приймає чистий текст, файли зображень та аудіофайли.
- **Транскрипція аудіо:** Перетворює голосові повідомлення в текст перед тим, як пропустити його через текстовий пайплайн модерації.
- **Агрегований конвеєр модерації:** 
  - **Аналіз токсичності:** Виявляє мову ворожнечі, образи та погрози.
  - **Фільтр ненормативної лексики:** Перевіряє наявність заборонених слів.
  - **Виявлення шахрайства:** Ідентифікує фішинг або шахрайські патерни.
  - **Аналіз тональності:** Визначає, чи є тон тексту позитивним, негативним чи нейтральним.
  - **Аналіз зображень:** Використовує ML для класифікації завантажених зображень.
- **Інтернаціоналізація (i18n):** Інтерфейс користувача доступний кількома мовами (англійською та українською) з використанням файлів cookie та словників перекладу.
- **Детальна звітність:** Генерує унікальний ID модерації для кожного запиту, зберігає детальні результати у JSON та дозволяє експортувати звіт у PDF-файл.
- **Панель історії (Dashboard):** Ретроспективний перегляд усього проаналізованого контенту з агрегованою оцінкою.

### 5. Структура проекту та логіка
```text
diploma-project/
├── app/
│   ├── __init__.py
│   ├── config.py           # Змінні середовища та конфігурація додатку
│   ├── database.py         # Налаштування БД, асинхронний рушій SQLAlchemy
│   ├── i18n.py             # Інтернаціоналізація (англійська/українська)
│   ├── main.py             # Точка входу FastAPI, налаштування маршрутів (routes)
│   ├── schemas.py          # Pydantic моделі для валідації запитів/відповідей
│   ├── models/
│   │   └── moderation.py   # SQLAlchemy ORM моделі (наприклад, ModerationRecord)
│   └── services/           # Шар бізнес-логіки
│       ├── aggregator.py       # Оркестратор: викликає всі сервіси і підраховує підсумковий бал ризику
│       ├── audio_service.py    # Валідація аудіофайлів та генерація тексту (Speech-to-text)
│       ├── fraud_service.py    # Перевірка тексту на наявність шахрайства
│       ├── hf_service.py       # Базова інтеграція з Hugging Face API
│       ├── hf_toxicity.py      # Модель Hugging Face для виявлення токсичності
│       ├── hf_xray_service.py  # Модель Hugging Face для аналізу зображень
│       ├── pdf_service.py      # Логіка генерації PDF-звітів
│       ├── profanity_service.py# Перевірка тексту за списками заборонених слів
│       └── sentiment_service.py# Аналіз тональності за допомогою NLTK VADER
├── static/
│   └── style.css           # CSS стилі інтерфейсу
├── templates/              # HTML шаблони Jinja2
│   ├── base.html           # Головний макет (layout), навігація, перемикач мов
│   ├── dashboard.html      # Форма завантаження контенту (головна сторінка)
│   ├── error.html          # UI для відображення помилок
│   ├── history.html        # Таблиця попередніх модерацій
│   └── result.html         # Детальний перегляд результату конкретної модерації
├── Dockerfile              # Інструкції для збірки Docker-контейнера
├── docker-compose.yml      # Оркестрація контейнерів (Додаток + БД)
├── requirements.txt        # Python залежності
└── README.md               # Короткий посібник із запуску
```

### 6. Потік даних (Data Flow) / Бізнес-логіка
1. **Введення даних:** Користувач надсилає текст, зображення або аудіофайл через UI (маршрут `/`).
2. **Попередня обробка (якщо є):** Якщо завантажено аудіо, `audio_service` транскрибує його в текст.
3. **Агрегація (`aggregator.py`):** Система передає дані до агрегатора. 
   - Текст паралельно (або послідовно) надсилається до сервісів аналізу тональності, токсичності, шахрайства та ненормативної лексики.
   - Зображення надсилаються до `hf_xray_service.py` для класифікації.
4. **Прийняття рішення:** Кожен сервіс повертає локальні оцінки (scores) та прапорці (flags). Агрегатор обчислює статус (наприклад, ДОЗВОЛЕНО, ПОЗНАЧЕНО, ЗАБЛОКОВАНО) на основі зважених оцінок ризику.
5. **Збереження в БД:** Повний вхідний запит, результати окремих сервісів та кінцеве рішення зберігаються в базу даних з використанням моделі `ModerationRecord` через SQLAlchemy.
6. **Вивід результату:** Користувач перенаправляється на сторінку `/result/{id}`, де він може переглянути детальний розбір аналізу або завантажити PDF-звіт за адресою `/result/{id}/pdf`.
