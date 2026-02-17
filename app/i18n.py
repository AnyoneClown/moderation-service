"""
app/i18n.py — Lightweight internationalisation (i18n) support.

Provides English and Ukrainian translations for all user-facing strings.
The active language is determined by a ``lang`` cookie (defaults to ``en``).
Templates receive a flat ``t`` dict of translations.
"""

from __future__ import annotations

# ────────────────────────────────────────────────────────────
# Translation dictionaries
# ────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # ── Global / nav ──
        "site_title": "AI Content Moderation",
        "nav_brand": "🛡️ AI Moderation",
        "nav_dashboard": "Dashboard",
        "nav_history": "History",
        "footer": "AI Content Moderation System — Diploma Project © 2026",
        "lang_label": "UA",
        "lang_switch_to": "uk",

        # ── Dashboard ──
        "dash_title": "Content Moderation Dashboard",
        "dash_subtitle": (
            "Submit any social-media post, text snippet, or image below. The system will "
            "analyse it using independent checks — <strong>Toxicity Detection</strong>, "
            "<strong>Spam Classification</strong>, <strong>Profanity Filtering</strong>, "
            "<strong>Fraud / Scam Detection</strong>, <strong>Sentiment Analysis</strong>, "
            "and <strong>Image Safety Analysis</strong> — all running in parallel."
        ),
        "dash_examples_label": "Try an example:",
        "example_friendly": "✅ Friendly message",
        "example_friendly_text": "Hello, great post! I really enjoyed reading your article about gardening tips. Keep up the good work!",
        "example_scam": "🕵️ Scam / Fraud",
        "example_scam_text": "CONGRATULATIONS! You've won a $50,000 prize! Send your bank account details and a $99 processing fee to claim NOW! Limited time only!",
        "example_toxic": "🧪 Toxic content",
        "example_toxic_text": "You're all idiots and I hope terrible things happen to every single one of you. This world would be better off without people like you.",
        "example_phishing": "🎣 Phishing",
        "example_phishing_text": "URGENT: Your PayPal account has been compromised. Click http://paypa1-secure.tk/verify to restore access immediately or your account will be permanently suspended within 24 hours!",
        "example_spam_fraud": "📧 Spam + Fraud",
        "example_spam_fraud_text": "🔥 LIMITED TIME: Invest $100 in crypto and get $10,000 back guaranteed! No risk! 100% safe! Send bitcoin now to double your money. DM me for details!",
        "label_text": "Text to moderate",
        "label_text_hint": "(optional if image is provided)",
        "placeholder_text": "Paste or type the content you want to check…",
        "max_chars": "Max 5 000 characters.",
        "label_image": "Upload image",
        "label_image_hint": "(optional — JPEG, PNG, GIF, WebP, max 10 MB)",
        "drop_zone_text": "Drag & drop an image here, or",
        "drop_zone_click": "click to browse",
        "drop_zone_formats": "Supported: JPEG, PNG, GIF, WebP",
        "remove_image": "✕ Remove image",
        "btn_analyse": "🔍 Analyse Content",

        # ── Result ──
        "back_new": "← New analysis",
        "result_title": "Moderation Result",
        "partial_warning": "⚠️ <strong>Partial Result</strong> — One or more external APIs were unavailable. The score was calculated using the remaining sources only.",
        "final_verdict": "Final Verdict",
        "aggregate_score": "Aggregate Score",
        "input_type_both": "📝 Text + 🖼️ Image",
        "input_type_image": "🖼️ Image Only",
        "input_type_text": "📝 Text Only",
        "submitted_text": "Submitted Text",
        "uploaded_image": "Uploaded Image",
        "source_breakdown": "Source Breakdown",
        "lbl_toxicity": "🧪 Toxicity (HF)",
        "lbl_spam": "📧 Spam (HF)",
        "lbl_profanity": "🤬 Profanity",
        "lbl_fraud": "🕵️ Fraud / Scam",
        "lbl_sentiment": "💬 Sentiment Risk",
        "lbl_nsfw": "🖼️ Image NSFW",
        "lbl_img_scam": "🖼️ Image Scam Risk",
        "ai_caption": "AI Image Caption",
        "suspicious_kw": "⚠ Suspicious keywords detected:",
        "show_raw_json": "Show raw analysis details (JSON)",
        "toxicity_details": "Toxicity details",
        "spam_details": "Spam details",
        "profanity_details": "Profanity details",
        "fraud_details": "Fraud / Scam details",
        "sentiment_details": "Sentiment details",
        "image_details": "Image analysis details",
        "record_id_label": "Record ID:",
        "analysed_at": "Analysed at:",
        "btn_new_analysis": "New Analysis",
        "btn_view_history": "View History",
        "btn_export_pdf": "📄 Export PDF",

        # ── PDF report ──
        "pdf_title": "🛡️ AI Content Moderation Report",
        "pdf_generated_from": "Generated from analysis performed on",
        "pdf_partial_warning": "⚠ Partial Result — One or more external APIs were unavailable. The score was calculated using the remaining sources.",
        "pdf_input_type": "Input Type:",
        "pdf_submitted_text": "Submitted Text",
        "pdf_score_breakdown": "Source Score Breakdown",
        "pdf_col_source": "Source",
        "pdf_col_score": "Score",
        "pdf_col_visual": "Visual",
        "pdf_image_caption": "Image Caption (AI-generated)",
        "pdf_record_id": "Record ID:",
        "pdf_analysed_at": "Analysed at:",
        "pdf_footer": "AI Content Moderation System — Diploma Project © 2026",

        # ── History ──
        "history_title": "Moderation History",
        "btn_new_plus": "+ New Analysis",
        "no_records": "No records yet.",
        "no_records_hint": 'Submit some text on the <a href="/" class="text-indigo-500 hover:underline">Dashboard</a> to get started.',
        "col_text": "Text (preview)",
        "col_type": "Type",
        "col_score": "Score",
        "col_status": "Status",
        "col_partial": "Partial?",
        "col_date": "Date",
        "partial_yes": "⚠ Yes",
        "image_only_label": "Image only",
        "details_link": "Details →",

        # ── Error ──
        "error_title": "Something went wrong",
        "btn_back_dashboard": "Back to Dashboard",
        "err_no_input": "Please provide text or an image to analyse.",
        "err_unsupported_image": "Unsupported image type:",
        "err_image_too_large": "Image exceeds 10 MB limit.",
        "err_not_found": "Record not found.",
    },

    "uk": {
        # ── Global / nav ──
        "site_title": "ШІ Модерація Контенту",
        "nav_brand": "🛡️ ШІ Модерація",
        "nav_dashboard": "Панель",
        "nav_history": "Історія",
        "footer": "Система ШІ Модерації Контенту — Дипломний Проєкт © 2026",
        "lang_label": "EN",
        "lang_switch_to": "en",

        # ── Dashboard ──
        "dash_title": "Панель Модерації Контенту",
        "dash_subtitle": (
            "Надішліть будь-який пост з соціальних мереж, текстовий фрагмент або зображення нижче. "
            "Система проаналізує його за допомогою незалежних перевірок — "
            "<strong>Виявлення Токсичності</strong>, <strong>Класифікація Спаму</strong>, "
            "<strong>Фільтр Нецензурної Лексики</strong>, <strong>Виявлення Шахрайства</strong>, "
            "<strong>Аналіз Настрою</strong> та <strong>Аналіз Безпеки Зображень</strong> — "
            "усі працюють паралельно."
        ),
        "dash_examples_label": "Спробуйте приклад:",
        "example_friendly": "✅ Дружнє повідомлення",
        "example_friendly_text": "Привіт, чудовий пост! Мені дуже сподобалась ваша стаття про поради з садівництва. Так тримати!",
        "example_scam": "🕵️ Шахрайство",
        "example_scam_text": "ВІТАЄМО! Ви виграли 50 000 грн! Надішліть реквізити банківського рахунку та 99 грн за обробку, щоб отримати приз ЗАРАЗ! Обмежений час!",
        "example_toxic": "🧪 Токсичний контент",
        "example_toxic_text": "Ви всі ідіоти і я сподіваюсь з вами трапиться щось жахливе. Світ був би кращим без таких людей як ви.",
        "example_phishing": "🎣 Фішинг",
        "example_phishing_text": "ТЕРМІНОВО: Ваш акаунт ПриватБанк було зламано. Перейдіть за посиланням http://privatbank-secure.tk/verify щоб відновити доступ негайно або ваш акаунт буде заблоковано протягом 24 годин!",
        "example_spam_fraud": "📧 Спам + Шахрайство",
        "example_spam_fraud_text": "🔥 ОБМЕЖЕНИЙ ЧАС: Інвестуйте 100$ в крипту і отримайте 10 000$ гарантовано! Без ризику! 100% безпечно! Надішліть біткоін зараз, щоб подвоїти свої гроші!",
        "label_text": "Текст для модерації",
        "label_text_hint": "(необов'язково, якщо є зображення)",
        "placeholder_text": "Вставте або введіть контент для перевірки…",
        "max_chars": "Максимум 5 000 символів.",
        "label_image": "Завантажити зображення",
        "label_image_hint": "(необов'язково — JPEG, PNG, GIF, WebP, макс. 10 МБ)",
        "drop_zone_text": "Перетягніть зображення сюди, або",
        "drop_zone_click": "натисніть для вибору",
        "drop_zone_formats": "Підтримується: JPEG, PNG, GIF, WebP",
        "remove_image": "✕ Видалити зображення",
        "btn_analyse": "🔍 Аналізувати Контент",

        # ── Result ──
        "back_new": "← Новий аналіз",
        "result_title": "Результат Модерації",
        "partial_warning": "⚠️ <strong>Частковий Результат</strong> — Один або кілька зовнішніх API були недоступні. Оцінка розрахована з використанням решти джерел.",
        "final_verdict": "Фінальний Вердикт",
        "aggregate_score": "Загальна Оцінка",
        "input_type_both": "📝 Текст + 🖼️ Зображення",
        "input_type_image": "🖼️ Лише Зображення",
        "input_type_text": "📝 Лише Текст",
        "submitted_text": "Наданий Текст",
        "uploaded_image": "Завантажене Зображення",
        "source_breakdown": "Розбивка по Джерелах",
        "lbl_toxicity": "🧪 Токсичність (HF)",
        "lbl_spam": "📧 Спам (HF)",
        "lbl_profanity": "🤬 Нецензурна лексика",
        "lbl_fraud": "🕵️ Шахрайство",
        "lbl_sentiment": "💬 Ризик Настрою",
        "lbl_nsfw": "🖼️ NSFW Зображення",
        "lbl_img_scam": "🖼️ Шахрайство Зображення",
        "ai_caption": "ШІ Опис Зображення",
        "suspicious_kw": "⚠ Виявлено підозрілі ключові слова:",
        "show_raw_json": "Показати деталі аналізу (JSON)",
        "toxicity_details": "Деталі токсичності",
        "spam_details": "Деталі спаму",
        "profanity_details": "Деталі нецензурної лексики",
        "fraud_details": "Деталі шахрайства",
        "sentiment_details": "Деталі настрою",
        "image_details": "Деталі аналізу зображення",
        "record_id_label": "ID Запису:",
        "analysed_at": "Проаналізовано:",
        "btn_new_analysis": "Новий Аналіз",
        "btn_view_history": "Переглянути Історію",
        "btn_export_pdf": "📄 Експорт PDF",

        # ── PDF report ──
        "pdf_title": "🛡️ Звіт ШІ Модерації Контенту",
        "pdf_generated_from": "Створено на основі аналізу, проведеного",
        "pdf_partial_warning": "⚠ Частковий Результат — Один або кілька зовнішніх API були недоступні. Оцінка розрахована з використанням решти джерел.",
        "pdf_input_type": "Тип Вхідних Даних:",
        "pdf_submitted_text": "Наданий Текст",
        "pdf_score_breakdown": "Розбивка Оцінок по Джерелах",
        "pdf_col_source": "Джерело",
        "pdf_col_score": "Оцінка",
        "pdf_col_visual": "Візуалізація",
        "pdf_image_caption": "Опис Зображення (ШІ)",
        "pdf_record_id": "ID Запису:",
        "pdf_analysed_at": "Проаналізовано:",
        "pdf_footer": "Система ШІ Модерації Контенту — Дипломний Проєкт © 2026",

        # ── History ──
        "history_title": "Історія Модерації",
        "btn_new_plus": "+ Новий Аналіз",
        "no_records": "Записів ще немає.",
        "no_records_hint": 'Надішліть текст на <a href="/" class="text-indigo-500 hover:underline">Панелі</a> щоб почати.',
        "col_text": "Текст (попередній перегляд)",
        "col_type": "Тип",
        "col_score": "Оцінка",
        "col_status": "Статус",
        "col_partial": "Частково?",
        "col_date": "Дата",
        "partial_yes": "⚠ Так",
        "image_only_label": "Лише зображення",
        "details_link": "Детальніше →",

        # ── Error ──
        "error_title": "Щось пішло не так",
        "btn_back_dashboard": "На Панель",
        "err_no_input": "Будь ласка, надайте текст або зображення для аналізу.",
        "err_unsupported_image": "Непідтримуваний тип зображення:",
        "err_image_too_large": "Зображення перевищує ліміт 10 МБ.",
        "err_not_found": "Запис не знайдено.",
    },
}

SUPPORTED_LANGUAGES = set(TRANSLATIONS.keys())
DEFAULT_LANGUAGE = "en"


def get_translations(lang: str) -> dict[str, str]:
    """Return the translation dict for the given language code."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return TRANSLATIONS[lang]
