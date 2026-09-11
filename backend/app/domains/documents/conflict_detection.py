"""
Детекция конфликта между treatment_modality и clinical_pathway.

Реализует правило из обсуждения: методика лечения (SRT/SRS -- "радиохирургия")
сама по себе не должна автоматически присваивать наивысший приоритет, если
клинический путь указывает на плановый послеоперационный случай без острой
симптоматики. Когда такой конфликт обнаружен, система НЕ выбирает категорию
сама -- она обязана показать оба сигнала врачу и потребовать явного решения.
"""

# Методы, для которых само название ("радиохирургия") может ошибочно
# восприниматься как автоматический маркер наивысшей срочности.
RADIOSURGERY_LIKE_MODALITIES = {"SRT", "SRS"}

# Пути, которые явно НЕ являются acute -- если модальность из списка выше
# сочетается с одним из этих путей, это потенциальный конфликт восприятия.
NON_ACUTE_PATHWAYS = {"awaiting_lab_results", "post_surgery_planned", "post_chemo_hormone"}


def detect_signal_conflict(
    treatment_modality: str,
    clinical_pathway: str | None,
    urgency_signals: dict,
) -> dict | None:
    """
    Возвращает dict с описанием конфликта, если он обнаружен, иначе None.

    Конфликт фиксируется, когда:
    - метод лечения похож на "радиохирургию" (SRT/SRS), И
    - клинический путь при этом явно не острый, И
    - явные признаки острой симптоматики (боль/кровотечение/сдавление) отсутствуют.

    Именно такое сочетание было в реальном документе-примере (менингиома,
    SRT 5 сеансов, плановое продолжение после операции, ECOG 1, хронические жалобы).
    """
    if treatment_modality not in RADIOSURGERY_LIKE_MODALITIES:
        return None

    if clinical_pathway not in NON_ACUTE_PATHWAYS:
        return None

    has_acute_signal = bool(
        urgency_signals.get("pain_or_bleeding_mentioned")
        or urgency_signals.get("mass_effect_or_compression")
    )
    if has_acute_signal:
        # Есть явный острый сигнал несмотря на "плановый" pathway -- пусть тоже
        # разбирает врач, но это отдельная категория конфликта (не самая частая).
        return {
            "reason": "modality_radiosurgery_but_acute_signal_present_despite_planned_pathway",
            "requires_mandatory_doctor_decision": True,
        }

    return {
        "reason": "modality_suggests_urgent_but_pathway_and_signals_suggest_planned",
        "requires_mandatory_doctor_decision": True,
        "explanation": (
            f"Метод лечения '{treatment_modality}' исторически ассоциируется с наивысшим "
            f"приоритетом ('радиохирургия'), но клинический путь ('{clinical_pathway}') и "
            "отсутствие острых сигналов указывают на плановый случай. Требуется решение врача."
        ),
    }
