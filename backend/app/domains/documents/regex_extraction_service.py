import re
from datetime import date, datetime

# ИИН РК: ровно 12 цифр. В отличие от ИНН РФ (10/12 цифр с контрольной суммой
# по другому алгоритму), у казахстанского ИИН контрольная цифра считается
# по своему алгоритму (модуль 11 с весовыми коэффициентами) -- реализуем ниже.
IIN_PATTERN = re.compile(r"\b\d{12}\b")

# Даты в формате ДД.ММ.ГГГГ, как в мед. картах формы №001/у
DATE_PATTERN = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")

# Код МКБ-10, например (C70.0), (C02.1) -- в скобках, буква + 2 цифры + точка + цифра
ICD10_PATTERN = re.compile(r"\(([A-Z]\d{2}\.\d)\s*\)")


def validate_iin_checksum(iin: str) -> bool:
    """
    Проверка контрольной суммы ИИН РК (алгоритм модуль-11 с двумя наборами весов).
    Возвращает False, если чек-сумма не сходится -- сигнал для понижения
    confidence поля перед показом врачу, не автоматический reject.
    """
    if not re.fullmatch(r"\d{12}", iin):
        return False

    weights_1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    digits = [int(d) for d in iin[:11]]
    control = int(iin[11])

    total = sum(d * w for d, w in zip(digits, weights_1))
    remainder = total % 11

    if remainder == 10:
        weights_2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        total = sum(d * w for d, w in zip(digits, weights_2))
        remainder = total % 11
        if remainder == 10:
            return False  # по стандарту считается невалидным

    return remainder == control


def extract_iin_candidates(text: str) -> list[dict]:
    """
    Возвращает список кандидатов на ИИН с пометкой, прошла ли чек-сумма.
    Несколько кандидатов -- частая ситуация в мед. картах (могут упоминаться
    ИИН лечащего врача, других сотрудников и т.д.), поэтому не выбираем
    первый найденный автоматически -- отдаём все врачу с confidence-меткой.
    """
    candidates = []
    for match in IIN_PATTERN.finditer(text):
        iin = match.group()
        candidates.append(
            {
                "value": iin,
                "checksum_valid": validate_iin_checksum(iin),
                "position": match.start(),
            }
        )
    return candidates


def extract_dates(text: str) -> list[date]:
    """Извлекает все даты формата ДД.ММ.ГГГГ, отбрасывая невалидные (напр. 31.02.2025)."""
    results = []
    for day_str, month_str, year_str in DATE_PATTERN.findall(text):
        try:
            results.append(date(int(year_str), int(month_str), int(day_str)))
        except ValueError:
            continue
    return results


def extract_icd10_codes(text: str) -> list[str]:
    """Извлекает коды МКБ-10 в формате (C70.0), как они встречаются в форме №001/у."""
    return list(dict.fromkeys(ICD10_PATTERN.findall(text)))  # dedup, сохраняя порядок
