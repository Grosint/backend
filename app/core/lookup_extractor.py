from __future__ import annotations

import re
from typing import Any

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def extract_items(raw_response: dict[str, Any], spec: dict[str, Any]) -> list[dict]:
    source_default = spec.get("source", "unknown")
    fields = spec.get("fields", [])
    items: list[dict] = []

    for field in fields:
        when = field.get("when")
        if when and not _when_matches(raw_response, when):
            continue

        if "value" in field:
            values = [field.get("value")]
        else:
            paths = field.get("paths") or []
            path = field.get("path")
            if path:
                paths = [path]

            if not paths:
                continue

            values = []
            for entry in paths:
                extracted = _extract_path_values(raw_response, entry)
                if extracted:
                    values.extend(extracted)
                    if field.get("first_only"):
                        break

            if not values:
                values = [field.get("default", "Not Available")]

        for value in values:
            null_if = field.get("null_if")
            if null_if is not None:
                null_values = null_if if isinstance(null_if, list) else [null_if]
                if value in null_values:
                    value = None
            if value is None or value == "" or value == [] or value == {}:
                value = field.get("default", "Not Available")

            if field.get("transform") == "yes_no":
                if value is True:
                    value = "Yes"
                elif value is False:
                    value = "No"
                elif value is None:
                    value = field.get("default", "Not Available")

            if field.get("match") == "email":
                value_str = str(value)
                if not EMAIL_PATTERN.match(value_str):
                    continue

            if field.get("stringify") or isinstance(value, (dict, list)):
                value = str(value)

            category = field.get("category", "TEXT")
            item_source = field.get("source", source_default)
            source_or_type = field.get("sourceOrType", "type")
            items.append(
                {
                    "source": item_source,
                    "type": field.get("type", "unknown"),
                    "value": str(value),
                    "sourceOrType": source_or_type,
                    "category": category,
                }
            )

    return items


def _extract_path_values(data: Any, path: str) -> list[Any]:
    tokens = [t for t in path.split(".") if t]
    current_values = [data]

    for token in tokens:
        next_values: list[Any] = []
        is_list = token.endswith("[]")
        key = token[:-2] if is_list else token

        for current in current_values:
            value = current.get(key) if isinstance(current, dict) else None

            if is_list:
                if isinstance(value, list):
                    next_values.extend(value)
            else:
                if value is not None:
                    next_values.append(value)

        current_values = next_values

        if not current_values:
            break

    return current_values


def _when_matches(raw_response: dict[str, Any], when: dict[str, Any]) -> bool:
    path = when.get("path")
    if not path:
        return True
    values = _extract_path_values(raw_response, path)
    if not values:
        return False

    expected = when.get("equals")
    not_equals = when.get("not_equals")

    for value in values:
        if expected is not None and value == expected:
            return True
        if not_equals is not None and value != not_equals:
            return True

    return False
