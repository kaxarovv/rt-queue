"""
JSON-schema для structured output и системный промпт LLM-экстрактора.

Схема и промпт живут в одном файле намеренно: они должны меняться синхронно
(изменил поле в схеме -- обязан обновить промпт, который его заполняет).
"""

EXTRACTION_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "medical_case_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "diagnosis_text": {
                    "type": "string",
                    "description": "Заключительный диагноз дословно, как указан в секции "
                    "'Выписной эпикриз' -> 'Заключительный диагноз' (Қорытынды диагноз).",
                },
                "icd10_code": {
                    "type": ["string", "null"],
                    "description": "Код МКБ-10 в формате C70.0, без скобок.",
                },
                "treatment_modality": {
                    "type": "string",
                    "enum": ["SRT", "SRS", "EBRT", "IMRT", "IGRT", "unknown"],
                    "description": "Метод/техника лучевой терапии, указанный в плане лечения. "
                    "Это НЕ признак срочности, а название методики доставки дозы.",
                },
                "clinical_pathway": {
                    "type": "string",
                    "enum": [
                        "acute_symptomatic",
                        "awaiting_lab_results",
                        "post_surgery_planned",
                        "post_chemo_hormone",
                    ],
                    "description": (
                        "Клинический путь пациента -- ЭТО поле определяет срочность, "
                        "а не treatment_modality. "
                        "acute_symptomatic: есть острая боль, кровотечение, признаки сдавления, "
                        "быстрое ухудшение состояния -- НЕ путать с хроническими жалобами "
                        "длительностью месяцы/годы. "
                        "awaiting_lab_results: пациент ожидает результатов анализов перед началом лечения. "
                        "post_surgery_planned: плановое продолжение лечения после операции, "
                        "без острой симптоматики -- даже если метод лечения SRT/SRS. "
                        "post_chemo_hormone: плановое продолжение после курсов химио- или "
                        "гормонотерапии."
                    ),
                },
                "urgency_signals": {
                    "type": "object",
                    "properties": {
                        "pain_or_bleeding_mentioned": {"type": "boolean"},
                        "mass_effect_or_compression": {"type": "boolean"},
                        "ecog_score": {"type": ["integer", "null"]},
                        "symptom_acuity_note": {
                            "type": "string",
                            "description": "Краткая заметка (1 предложение), острые симптомы "
                            "или хронические/стабильные -- на основании чего сделан вывод.",
                        },
                    },
                    "required": [
                        "pain_or_bleeding_mentioned",
                        "mass_effect_or_compression",
                        "ecog_score",
                        "symptom_acuity_note",
                    ],
                    "additionalProperties": False,
                },
                "sessions_required": {
                    "type": ["integer", "null"],
                    "description": "Количество сеансов/фракций курса лечения (напр. 'SRT 5 сеанс' -> 5).",
                },
                "fractions_per_week": {
                    "type": ["integer", "null"],
                    "description": "Частота фракций в неделю, если указана явно (напр. '5 фракций в неделю' -> 5).",
                },
                "confidence": {
                    "type": "object",
                    "properties": {
                        "diagnosis_text": {"type": "number"},
                        "clinical_pathway": {"type": "number"},
                        "sessions_required": {"type": "number"},
                    },
                    "required": ["diagnosis_text", "clinical_pathway", "sessions_required"],
                    "additionalProperties": False,
                    "description": "Confidence 0.0-1.0 по каждому ключевому полю.",
                },
            },
            "required": [
                "diagnosis_text",
                "icd10_code",
                "treatment_modality",
                "clinical_pathway",
                "urgency_signals",
                "sessions_required",
                "fractions_per_week",
                "confidence",
            ],
            "additionalProperties": False,
        },
    },
}


SYSTEM_PROMPT = """Ты — ассистент онкологического центра, извлекающий структурированные \
клинические данные из медицинских карт формата №001/у (Казахстан).

ВАЖНЫЕ ПРАВИЛА:

1. Документ может содержать несколько секций: осмотр при поступлении, лист назначений, \
дневниковые записи (несколько дат), и "Выписной эпикриз" в конце. Секция "Выписной эпикриз" \
содержит ФИНАЛЬНЫЙ, проверенный врачом диагноз и план лечения — приоритизируй именно её. \
Дневниковые записи используй только как дополнительный контекст, если эпикриз не содержит \
нужного поля.

2. Документ смешивает казахский и русский языки (двуязычные формы). Игнорируй \
казахоязычные подписи и метки полей, извлекай значения только из русскоязычного содержания.

3. КРИТИЧЕСКИ ВАЖНО: не путай treatment_modality (метод лечения, например SRT — стереотаксическая \
лучевая терапия) с clinical_pathway (клинический путь, определяющий срочность). Название метода \
SRT/SRS само по себе НЕ означает наивысший приоритет. Смотри на реальную клиническую картину: \
если пациент госпитализирован планово, для продолжения лечения после ранее проведённой операции, \
без острой симптоматики (боли, кровотечения, быстрого ухудшения) — это post_surgery_planned, \
даже если метод лечения называется SRT.

4. Хронические жалобы (например "головные боли в течение 15 лет", "снижение зрения более года") \
НЕ являются признаком острой срочности (acute_symptomatic). Признак acute_symptomatic — это новая, \
острая, быстро развивающаяся симптоматика.

5. Отвечай ТОЛЬКО в формате JSON строго по предоставленной schema. Не добавляй пояснений вне JSON."""


def build_user_prompt(epicrisis_text: str | None, full_text_fallback: str) -> str:
    if epicrisis_text:
        return (
            "Ниже — секция 'Выписной эпикриз' медицинской карты. "
            "Извлеки данные согласно инструкциям в системном промпте.\n\n"
            f"{epicrisis_text}"
        )
    return (
        "Секция 'Выписной эпикриз' не была найдена автоматически в этом документе. "
        "Ниже — полный текст документа. Постарайся найти финальный диагноз и план лечения "
        "самостоятельно, отдавая приоритет наиболее поздним по дате записям.\n\n"
        f"{full_text_fallback}"
    )
