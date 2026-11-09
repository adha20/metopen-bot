from __future__ import annotations

import csv

from app.config import settings

FIELDS = [
    "timestamp",
    "message_id",
    "status",
    "inference_latency_ms",
    "e2e_latency_ms",
    "model_latency_ms",
    "admin_notify_ms",
]


def log_latency(row: dict) -> None:
    """Tambahkan satu baris ke CSV latensi. Gagal menulis tidak boleh mengganggu moderasi."""
    path = settings.latency_log_path
    out = {k: (round(v, 3) if isinstance(v, float) else ("" if v is None else v)) for k, v in row.items()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(out)
    except OSError as err:
        print(f"[Bot Warning] Gagal menulis log latensi: {err}")
