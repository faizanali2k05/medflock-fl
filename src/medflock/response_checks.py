"""Flag suspicious unit changes without silently rewriting clinical text."""

import re

QUANTITY = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(ng/mL|ng/L|mg/dL|mg/L|mmol/L|µmol/L|umol/L)\b",
    re.IGNORECASE,
)


def unit_warnings(source, answer):
    stated = {}
    for value, unit in QUANTITY.findall(source):
        stated.setdefault(float(value), set()).add(unit.lower())
    warnings = []
    for value, unit in QUANTITY.findall(answer):
        original = stated.get(float(value))
        if original and unit.lower() not in original:
            message = (
                f"Check {value} {unit}: the source uses {', '.join(sorted(original))} "
                "for this numeric value. The assistant may have changed a unit. "
                "Verify against the original case before using this draft."
            )
            if message not in warnings:
                warnings.append(message)
    return warnings


class RepetitionError(ValueError):
    pass


def reject_repetition(text):
    """Stop repeated sentence/bullet loops without removing clinical values or rewriting claims."""
    from collections import Counter

    parts = re.split(r"[\n.!?]+|\s+[*•]\s+", text[-12000:])
    normalized = [re.sub(r"[^a-z0-9 ]", "", part.lower()).strip() for part in parts]
    counts = Counter(part for part in normalized if len(part.split()) >= 7)
    if any(count >= 3 for count in counts.values()):
        raise RepetitionError("Model repetition detected")
    words = re.findall(r"\w+", text.lower())
    for width in [12, 24, 48]:
        if len(words) >= width * 3:
            tail = words[-width:]
            if words[-width * 2 : -width] == tail == words[-width * 3 : -width * 2]:
                raise RepetitionError("Model repetition detected")
