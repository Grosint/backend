from __future__ import annotations

from typing import Any


def normalize_source_or_type(data: Any) -> Any:
    if isinstance(data, list):
        return [normalize_source_or_type(item) for item in data]

    if isinstance(data, dict):
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if key == "showSource":
                normalized["sourceOrType"] = "source" if value else "type"
                continue

            normalized[key] = normalize_source_or_type(value)

        if (
            "source" in normalized
            and "type" in normalized
            and "value" in normalized
            and "sourceOrType" not in normalized
        ):
            normalized["sourceOrType"] = "type"

        return normalized

    return data
