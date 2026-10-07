"""Нормализация номера линии — без тяжёлых зависимостей (удобно для APK)."""


def normalize_phone(raw: str) -> str:
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def format_phone(digits: str) -> str:
    digits = normalize_phone(digits)
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    if digits:
        return "+" + digits
    return "—"
