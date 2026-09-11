import enum


class ClinicalPathway(str, enum.Enum):
    """
    Клинический путь пациента — то, ЧТО реально определяет срочность.
    Это НЕ метод лечения (см. TreatmentModality) — намеренно разделены,
    чтобы избежать конфликта вида "SRT => всегда наивысший приоритет",
    когда на деле это плановое продолжение лечения после операции.
    """

    ACUTE_SYMPTOMATIC = "acute_symptomatic"        # боль, кровотечение — наивысший приоритет
    AWAITING_LAB_RESULTS = "awaiting_lab_results"   # по мере готовности анализов, 1-2 недели
    POST_SURGERY_PLANNED = "post_surgery_planned"    # после операции, для профилактики, 1-2 мес
    POST_CHEMO_HORMONE = "post_chemo_hormone"         # после химио/гормонотерапии, через 3 мес


class TreatmentModality(str, enum.Enum):
    """
    Метод/техника лучевой терапии — метаданные о том, КАК будут лечить.
    Используется для планирования (длительность сеанса, оборудование),
    но НЕ определяет приоритет напрямую.
    """

    SRT = "SRT"          # стереотаксическая лучевая терапия (фракционированная)
    SRS = "SRS"          # стереотаксическая радиохирургия (обычно 1 фракция)
    EBRT = "EBRT"        # дистанционная лучевая терапия классическая
    IMRT = "IMRT"        # интенсивно-модулированная ЛТ
    IGRT = "IGRT"        # ЛТ под визуализационным контролем
    UNKNOWN = "unknown"


class PriorityCategory(str, enum.Enum):
    """Финальная категория приоритета — то, что реально используется в scheduling."""

    IMMEDIATE = "immediate"            # боль/кровотечение/радиохирургия по факту остроты
    URGENT_1_2_WEEKS = "urgent_1_2w"    # по готовности анализов
    PLANNED_1_2_MONTHS = "planned_1_2m"  # после операции, профилактика
    LOW_3_MONTHS = "low_3m"               # после химио/гормонотерапии

    @property
    def base_score(self) -> int:
        return {
            PriorityCategory.IMMEDIATE: 1000,
            PriorityCategory.URGENT_1_2_WEEKS: 750,
            PriorityCategory.PLANNED_1_2_MONTHS: 500,
            PriorityCategory.LOW_3_MONTHS: 250,
        }[self]

    @property
    def max_wait_days(self) -> int:
        """Стартовые значения окон ожидания. В проде — переезжает в БД-конфиг."""
        return {
            PriorityCategory.IMMEDIATE: 3,
            PriorityCategory.URGENT_1_2_WEEKS: 14,
            PriorityCategory.PLANNED_1_2_MONTHS: 60,
            PriorityCategory.LOW_3_MONTHS: 90,
        }[self]


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    TEXT_EXTRACTED = "text_extracted"
    LLM_PROCESSED = "llm_processed"
    NEEDS_REVIEW = "needs_review"     # низкий confidence или конфликт сигналов
    REVIEWED = "reviewed"
    FAILED = "failed"


class CaseStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionStatus(str, enum.Enum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    MISSED = "missed"
    RESCHEDULED = "rescheduled"


class SlotStatus(str, enum.Enum):
    FREE = "free"
    BOOKED = "booked"
    BLOCKED_MAINTENANCE = "blocked_maintenance"
