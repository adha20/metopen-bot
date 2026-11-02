from __future__ import annotations

import argparse
import threading
import time

from app.config import settings
from app.database.db import init_db

MODES = ["all", "api", "bot"]


def run_api(port: int | None = None) -> None:
    """Menjalankan server FastAPI: API inferensi AI + Web Dashboard dalam satu port."""
    import uvicorn

    target_port = port or settings.api_port
    print(f"🚀 FastAPI (API + Dashboard) di http://{settings.api_host}:{target_port}")
    uvicorn.run("app.api.server:app", host=settings.api_host, port=target_port, log_level="info")


def run_bot() -> None:
    """Menjalankan Bot Discord."""
    if not settings.discord_bot_token:
        print("⚠️ [Peringatan] DISCORD_BOT_TOKEN belum diset di file .env. Bot Discord tidak dijalankan.")
        return

    from app.bot.discord_bot import run_discord_bot

    print("🤖 Menjalankan Bot Discord Gateway...")
    run_discord_bot()


def main() -> None:
    init_db()

    parser = argparse.ArgumentParser(description="Cyberbullying Discord Detector Runner")
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=settings.run_mode if settings.run_mode in MODES else "all",
        help="all (default): API + Dashboard + Bot | api: API + Dashboard saja | bot: Bot saja",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port kustom untuk server FastAPI (opsional, default: API_PORT / 8000)",
    )
    args = parser.parse_args()

    if args.mode == "api":
        run_api(args.port)
        return

    if args.mode == "bot":
        run_bot()
        return

    # Mode 'all': FastAPI di background thread, Bot di main thread
    print("=" * 60)
    print("🚀 MEMULAI SELURUH SISTEM MODERASI INDOBERT")
    print("=" * 60)

    api_thread = threading.Thread(target=run_api, args=(args.port,), daemon=True, name="FastAPI-Thread")
    api_thread.start()

    if settings.discord_bot_token:
        run_bot()
        return

    print("\n💡 Tips: Tambahkan DISCORD_BOT_TOKEN di .env untuk menyalakan bot Discord.")
    print("    Server aktif (Dashboard & API berjalan). Tekan Ctrl+C untuk menghentikan server.\n")
    try:
        while api_thread.is_alive():
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n🛑 Sistem dihentikan oleh pengguna.")


if __name__ == "__main__":
    main()
