#!/usr/bin/env python3
"""Skrip Pengujian Mandiri Otomatis untuk Web Dashboard & Database metopen-bot."""

from __future__ import annotations

import sys
from app.dashboard.routes import create_dashboard_app
from app.database.db import get_connection


def run_tests() -> None:
    print("=" * 60)
    print("🧪 MEMULAI PENGUJIAN WEB DASHBOARD & DATABASE METOPEN-BOT")
    print("=" * 60)

    # 1. Inisialisasi Aplikasi Flask
    print("[1/5] Menginisialisasi Flask App & Database SQLite...")
    app = create_dashboard_app()
    client = app.test_client()
    print("      ✅ Berhasil membuat aplikasi dashboard.")

    # 2. Uji Halaman Utama (HTML Rendering)
    print("[2/5] Menguji halaman utama (GET /)...")
    resp_index = client.get("/")
    assert resp_index.status_code == 200, f"Gagal memuat halaman utama: {resp_index.status_code}"
    assert b"Dashboard Admin" in resp_index.data, "Judul Dashboard Admin tidak ditemukan di HTML"
    assert b"Daftar Menu" in resp_index.data, "Kategori Daftar Menu tidak ditemukan di HTML"
    print(f"      ✅ Berhasil memuat HTML ({len(resp_index.data):,} bytes rendered).")

    # 3. Uji Endpoint REST API
    print("[3/5] Menguji endpoint statistik & antrean (REST API)...")
    resp_stats = client.get("/api/stats")
    assert resp_stats.status_code == 200, f"Gagal /api/stats: {resp_stats.status_code}"
    stats_data = resp_stats.get_json()
    print(f"      ✅ /api/stats -> total pesan: {stats_data.get('total_messages_today')}, ditinjau: {stats_data.get('flagged_count')}")

    resp_queue = client.get("/api/flagged-queue")
    assert resp_queue.status_code == 200, f"Gagal /api/flagged-queue: {resp_queue.status_code}"
    queue_data = resp_queue.get_json()
    print(f"      ✅ /api/flagged-queue -> {len(queue_data)} pesan menunggu moderasi.")

    resp_users = client.get("/api/users-summary")
    assert resp_users.status_code == 200, f"Gagal /api/users-summary: {resp_users.status_code}"
    users_data = resp_users.get_json()
    print(f"      ✅ /api/users-summary -> {len(users_data)} pengguna terdata.")

    # 4. Uji Aksi Moderasi Human-in-the-Loop (Review Action)
    print("[4/5] Menguji simulasi aksi moderasi admin (POST /api/actions/review)...")
    if queue_data:
        test_msg_id = queue_data[0]["message_id"]
        resp_act = client.post(
            "/api/actions/review",
            json={"message_id": test_msg_id, "action": "pardon", "notes": "Uji coba persetujuan otomatis oleh admin"},
        )
        assert resp_act.status_code == 200, f"Gagal review action: {resp_act.status_code}"
        updated_log = resp_act.get_json()
        print(f"      ✅ Berhasil mengubah status {test_msg_id} -> '{updated_log.get('status')}'.")

    # 5. Uji Integritas File Database SQLite & WAL Mode
    print("[5/5] Memeriksa integritas SQLite & WAL Mode...")
    with get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        logs_count = conn.execute("SELECT COUNT(*) FROM analysis_logs;").fetchone()[0]
        users_count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        assert journal_mode.upper() == "WAL", f"Journal mode bukan WAL: {journal_mode}"
        print(f"      ✅ Database SQLite terhubung (WAL mode: {journal_mode.upper()}, {logs_count} log, {users_count} user).")

    print("=" * 60)
    print("🎉 SEMUA PENGUJIAN SELESAI & BERHASIL 100%!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
