from __future__ import annotations

import argparse
import sys
import threading

from app.config import settings
from app.dashboard.routes import create_dashboard_app
from app.database.db import init_db


def run_api() -> None:
    """Menjalankan Microservice AI Inference FastAPI."""
    import uvicorn

    print(f"🚀 Menjalankan FastAPI Server di http://{settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "app.api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


def run_dashboard() -> None:
    """Menjalankan Web Dashboard Flask."""
    print(f"🌐 Menjalankan Web Dashboard di http://{settings.flask_host}:{settings.flask_port}")
    app = create_dashboard_app()
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.dashboard_debug,
        use_reloader=False,
    )


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
        choices=["all", "api", "bot", "dashboard"],
        default=settings.run_mode if settings.run_mode in ["all", "api", "bot", "dashboard"] else "all",
        help="Mode layanan yang ingin dijalankan: all (default), api, bot, dashboard",
    )
    args = parser.parse_args()
    mode = args.mode

    if mode == "api":
        run_api()
        return

    if mode == "dashboard":
        run_dashboard()
        return

    if mode == "bot":
        run_bot()
        return

    # Mode 'all': Jalankan API & Dashboard di background thread, Bot di main thread
    print("=" * 60)
    print("🚀 MEMULAI SELURUH SISTEM MODERASI INDOBERT (3-TIER ARCHITECTURE)")
    print("=" * 60)

    # 1. Thread FastAPI
    api_thread = threading.Thread(target=run_api, daemon=True, name="FastAPI-Thread")
    api_thread.start()

    # 2. Thread Dashboard
    dash_thread = threading.Thread(target=run_dashboard, daemon=True, name="Flask-Dashboard-Thread")
    dash_thread.start()

    # 3. Main Thread: Bot Discord
    if settings.discord_bot_token:
        run_bot()
    else:
        print("\n💡 Tips: Tambahkan DISCORD_BOT_TOKEN di .env untuk menyalakan bot Discord.")
        print("    Tekan Ctrl+C untuk menghentikan server API & Dashboard.\n")
        try:
            api_thread.join()
        except KeyboardInterrupt:
            print("\n🛑 Sistem dihentikan oleh pengguna.")


if __name__ == "__main__":
    main()
