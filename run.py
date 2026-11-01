from __future__ import annotations

import argparse
import sys
import threading

from app.config import settings
from app.dashboard.routes import create_dashboard_app
from app.database.db import init_db


def run_api() -> None:
    """Menjalankan Microservice AI Inference FastAPI."""
    try:
        import uvicorn
        print(f"🚀 Menjalankan FastAPI Server di http://{settings.api_host}:{settings.api_port}")
        uvicorn.run(
            "app.api.server:app",
            host=settings.api_host,
            port=settings.api_port,
            log_level="info",
        )
    except ModuleNotFoundError as e:
        print(f"⚠️ [Peringatan API] Modul '{e.name}' belum terpasang. API inferensi dinonaktifkan sementara.")
    except Exception as e:
        print(f"⚠️ [Peringatan API] Gagal menjalankan API: {e}")


def run_dashboard(port: int | None = None) -> None:
    """Menjalankan Web Dashboard Flask dengan auto-fallback jika port sibuk."""
    target_port = port or settings.flask_port
    app = create_dashboard_app()
    try:
        print(f"🌐 Menjalankan Web Dashboard di http://{settings.flask_host}:{target_port}")
        app.run(
            host=settings.flask_host,
            port=target_port,
            debug=settings.dashboard_debug,
            use_reloader=False,
        )
    except OSError as err:
        if err.errno == 98 or "Address already in use" in str(err):
            fallback_port = target_port + 1 if target_port != 5000 else 5001
            print(f"⚠️ Port {target_port} sedang digunakan. Mengalihkan otomatis ke port cadangan {fallback_port}...")
            print(f"🌐 Menjalankan Web Dashboard di http://{settings.flask_host}:{fallback_port}")
            app.run(
                host=settings.flask_host,
                port=fallback_port,
                debug=settings.dashboard_debug,
                use_reloader=False,
            )
        else:
            raise


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
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port kustom untuk Web Dashboard (opsional, default: FLASK_PORT / 5000)",
    )
    args = parser.parse_args()
    mode = args.mode

    if mode == "api":
        run_api()
        return

    if mode == "dashboard":
        run_dashboard(args.port)
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
    dash_thread = threading.Thread(target=run_dashboard, args=(args.port,), daemon=True, name="Flask-Dashboard-Thread")
    dash_thread.start()

    # 3. Main Thread: Bot Discord
    if settings.discord_bot_token:
        run_bot()
    else:
        print("\n💡 Tips: Tambahkan DISCORD_BOT_TOKEN di .env untuk menyalakan bot Discord.")
        print("    Server aktif (Dashboard & API berjalan). Tekan Ctrl+C untuk menghentikan server.\n")
        try:
            while dash_thread.is_alive():
                dash_thread.join(timeout=1.0)
        except KeyboardInterrupt:
            print("\n🛑 Sistem dihentikan oleh pengguna.")


if __name__ == "__main__":
    main()
