"""Canonical payload handling for pending-change safety."""
import hashlib
import json
from decimal import Decimal


def normalize_payload(value):
    if isinstance(value, dict):
        return {key: normalize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_payload(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        return int(number) if number == number.to_integral() else float(number)
    return value


def canonicalize_pending_payload(kind, payload):
    data = normalize_payload(payload)
    base_kind = kind.removeprefix("request:")
    if base_kind in {"rate_change", "po"} and isinstance(data, dict):
        for field in ("source_lang", "target_lang"):
            if data.get(field):
                data[field] = str(data[field]).upper()
    return data


def pending_fingerprint(kind, translator_id, payload):
    canonical = json.dumps(
        {"kind": kind, "translator_id": translator_id,
         "payload": canonicalize_pending_payload(kind, payload)},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
