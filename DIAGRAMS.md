# DIAGRAMS

## 1. Загальна архітектура системи

```mermaid
flowchart LR
    U[Користувач] --> B[Браузер]
    B --> F[FastAPI Web Application]
    F --> A[Aggregator]
    A --> T[HF Toxicity Service]
    A --> S[HF Spam Service]
    A --> P[NVIDIA NIM Profanity Service]
    A --> R[Fraud Detection Service]
    A --> M[Sentiment Service]
    A --> X[X-Ray Service]
    F --> AU[Audio Transcription Service]
    F --> DB[(PostgreSQL)]
    F --> PDF[PDF Report Service]
    DB --> H[History Page]
    PDF --> B
    H --> B
```

## 2. Use Case діаграма

```mermaid
flowchart LR
    user([Користувач])

    uc1((Відкрити панель модерації))
    uc2((Ввести текст))
    uc3((Завантажити аудіофайл))
    uc4((Записати аудіо))
    uc5((Запустити аналіз))
    uc6((Переглянути результат))
    uc7((Переглянути історію))
    uc8((Експортувати PDF))
    uc9((Змінити мову інтерфейсу))

    user --> uc1
    user --> uc2
    user --> uc3
    user --> uc4
    user --> uc5
    user --> uc6
    user --> uc7
    user --> uc8
    user --> uc9
```

## 3. Діаграма компонентів

```mermaid
flowchart TD
    UI[UI Layer<br/>Jinja2 Templates + Tailwind CSS]
    ROUTES[Presentation Layer<br/>FastAPI Routes]
    CORE[Business Layer<br/>Aggregator]
    AUDIO[Audio Module]
    TOX[Toxicity Module]
    SPAM[Spam Module]
    FRAUD[Fraud Module]
    PROF[Profanity Module]
    SENT[Sentiment Module]
    XRAY[X-Ray Module]
    DB[(PostgreSQL Database)]
    PDF[PDF Generator]
    CFG[Configuration Layer]

    UI --> ROUTES
    ROUTES --> AUDIO
    ROUTES --> CORE
    ROUTES --> PDF
    ROUTES --> DB

    CORE --> TOX
    CORE --> SPAM
    CORE --> FRAUD
    CORE --> PROF
    CORE --> SENT
    CORE --> XRAY

    AUDIO --> CORE
    CORE --> DB
    PDF --> DB
    CFG --> ROUTES
    CFG --> AUDIO
    CFG --> TOX
    CFG --> SPAM
    CFG --> FRAUD
    CFG --> PROF
```

## 4. Діаграма послідовності для текстового аналізу

```mermaid
sequenceDiagram
    participant U as Користувач
    participant B as Browser
    participant F as FastAPI
    participant A as Aggregator
    participant T as Toxicity
    participant S as Spam
    participant P as Profanity
    participant R as Fraud
    participant M as Sentiment
    participant X as X-Ray
    participant D as PostgreSQL

    U->>B: Вводить текст
    B->>F: POST /moderate
    F->>A: aggregate_moderation(text)
    par Паралельні перевірки
        A->>T: check_hf_toxicity()
        A->>S: check_hf_spam()
        A->>P: check_profanity()
        A->>R: check_fraud()
        A->>M: check_sentiment()
        A->>X: check_xray()
    end
    T-->>A: score
    S-->>A: score
    P-->>A: score + spans
    R-->>A: score
    M-->>A: score + spans
    X-->>A: highlighted spans
    A-->>F: final_score + status
    F->>D: save ModerationRecord
    F-->>B: Redirect /result/{id}
    B-->>U: Сторінка результату
```

## 5. Діаграма послідовності для аудіоаналізу

```mermaid
sequenceDiagram
    participant U as Користувач
    participant B as Browser
    participant F as FastAPI
    participant AU as Audio Service
    participant HF as Whisper API
    participant A as Aggregator
    participant D as PostgreSQL

    U->>B: Завантажує аудіо
    B->>F: POST /moderate-audio
    F->>AU: validate + transcribe_audio()
    AU->>HF: Надсилання аудіо
    HF-->>AU: Transcribed text
    AU-->>F: text + language
    F->>A: aggregate_moderation(text)
    A-->>F: final result
    F->>D: save ModerationRecord
    F-->>B: Redirect /result/{id}
    B-->>U: Сторінка результату
```

## 6. ER-діаграма

```mermaid
erDiagram
    MODERATION_RECORD {
        UUID id PK
        TEXT text
        VARCHAR input_type
        VARCHAR audio_language
        FLOAT toxicity_score
        FLOAT spam_score
        FLOAT profanity_score
        FLOAT fraud_score
        FLOAT sentiment_score
        JSON toxicity_details
        JSON spam_details
        JSON profanity_details
        JSON fraud_details
        JSON sentiment_details
        FLOAT final_score
        VARCHAR status
        VARCHAR is_partial
        TEXT xray_html
        TIMESTAMP created_at
    }
```

## 7. Діаграма розгортання

```mermaid
flowchart TD
    DEV[Розробник / Користувач]
    HOST[Host Machine]
    WEB[Docker Container: web]
    DB[Docker Container: db]
    API1[Hugging Face API]
    API2[NVIDIA NIM API]

    DEV --> HOST
    HOST --> WEB
    HOST --> DB
    WEB --> DB
    WEB --> API1
    WEB --> API2
```

## 8. Діаграма потоків даних

```mermaid
flowchart LR
    IN[Вхідні дані<br/>текст або аудіо] --> VALID[Валідація]
    VALID --> TRANS[Транскрипція аудіо]
    VALID --> AGGR[Агрегатор]
    TRANS --> AGGR
    AGGR --> ANALYSIS[Незалежні модулі аналізу]
    ANALYSIS --> SCORE[Розрахунок підсумкового бала]
    SCORE --> SAVE[Збереження результату]
    SAVE --> OUT[Сторінка результату / PDF / Історія]
```

## Примітка

Якщо потрібно, наступним кроком можна:

1. конвертувати ці Mermaid-діаграми в SVG або PNG;
2. вставити їх посиланнями прямо в `DIPLOMA.md`;
3. підготувати окремий варіант діаграм у стилі UML для draw.io.
