from __future__ import annotations


def format_duration(minutes: int | None) -> str:
    """Ubah menit menjadi label singkat: 90 -> '90 Menit', 120 -> '2 Jam', 0/None -> 'Permanen'."""
    if not minutes:
        return "Permanen"
    if minutes % 1440 == 0:
        return f"{minutes // 1440} Hari"
    if minutes % 60 == 0:
        return f"{minutes // 60} Jam"
    return f"{minutes} Menit"
