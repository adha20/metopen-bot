#!/usr/bin/env python3
"""Skrip Pengujian Mandiri Otomatis untuk Web Dashboard & Database metopen-bot.

PERINGATAN: memakai database dari DATABASE_PATH (default app.db) dan benar-benar mengubah datanya.
Jalankan pada salinan:  cp app.db /tmp/test.db && DATABASE_PATH=/tmp/test.db python test_dashboard.py
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.server import app
from app.database.db import get_connection, init_db


def run_tests() -> None:
    print("=" * 60)
    print("🧪 MEMULAI PENGUJIAN WEB DASHBOARD & DATABASE METOPEN-BOT")
    print("=" * 60)

    # 1. Inisialisasi Aplikasi FastAPI
    print("[1/5] Menginisialisasi FastAPI App & Database SQLite...")
    init_db()
    client = TestClient(app)  # tanpa `with` agar model IndoBERT tidak ikut dimuat
    print("      ✅ Berhasil membuat aplikasi dashboard.")

    # 2. Uji Halaman Utama (HTML Rendering)
    print("[2/5] Menguji halaman utama (GET /)...")
    resp_index = client.get("/")
    assert resp_index.status_code == 200, f"Gagal memuat halaman utama: {resp_index.status_code}"
    assert b"Dashboard Admin" in resp_index.content, "Judul Dashboard Admin tidak ditemukan di HTML"
    assert b"Daftar Menu" in resp_index.content, "Kategori Daftar Menu tidak ditemukan di HTML"
    print(f"      ✅ Berhasil memuat HTML ({len(resp_index.content):,} bytes rendered).")

    # 3. Uji Endpoint REST API
    print("[3/5] Menguji endpoint statistik & antrean (REST API)...")
    resp_stats = client.get("/api/stats")
    assert resp_stats.status_code == 200, f"Gagal /api/stats: {resp_stats.status_code}"
    stats_data = resp_stats.json()
    print(f"      ✅ /api/stats -> total pesan: {stats_data.get('total_messages_today')}, ditinjau: {stats_data.get('flagged_count')}")

    resp_queue = client.get("/api/flagged-queue")
    assert resp_queue.status_code == 200, f"Gagal /api/flagged-queue: {resp_queue.status_code}"
    queue_data = resp_queue.json()
    print(f"      ✅ /api/flagged-queue -> {len(queue_data)} pesan menunggu moderasi.")

    resp_users = client.get("/api/users-summary")
    assert resp_users.status_code == 200, f"Gagal /api/users-summary: {resp_users.status_code}"
    users_data = resp_users.json()
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
        updated_log = resp_act.json()
        print(f"      ✅ Berhasil mengubah status {test_msg_id} -> '{updated_log.get('status')}'.")

    # 5. Uji Integritas File Database SQLite & WAL Mode
    print("[5/6] Memeriksa integritas SQLite & WAL Mode...")
    with get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        logs_count = conn.execute("SELECT COUNT(*) FROM analysis_logs;").fetchone()[0]
        users_count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        assert journal_mode.upper() == "WAL", f"Journal mode bukan WAL: {journal_mode}"
        print(f"      ✅ Database SQLite terhubung (WAL mode: {journal_mode.upper()}, {logs_count} log, {users_count} user).")

    # 6. Uji Fitur Kontribusi Dataset & Ekspor CSV 13-Kolom
    print("[6/6] Menguji API Tambah ke Dataset & Ekspor CSV 13-Kolom...")
    with get_connection() as conn:
        conn.execute("DELETE FROM dataset_contributions WHERE tweet IN ('oi babi', 'halo selamat pagi kawan-kawan semuanya')")
        conn.commit()
    resp_add1 = client.post(
        "/api/dataset/add",
        json={
            "text": "oi babi",
            "labels": {"HS": 1, "Abusive": 1, "HS_Individual": 1, "HS_Strong": 1},
            "source_log_id": 1,
        },
    )
    assert resp_add1.status_code == 200, f"Gagal /api/dataset/add: {resp_add1.status_code}"
    data_add1 = resp_add1.json()
    assert data_add1.get("success") is True
    print(f"      ✅ Berhasil tambah entri toksik -> id: {data_add1.get('id')}, total: {data_add1.get('total')}")

    resp_add2 = client.post(
        "/api/dataset/add",
        json={
            "text": "halo selamat pagi kawan-kawan semuanya",
            "labels": {},
            "source_log_id": None,
        },
    )
    assert resp_add2.status_code == 200, f"Gagal /api/dataset/add false positive: {resp_add2.status_code}"
    data_add2 = resp_add2.json()
    assert data_add2.get("total") == data_add1.get("total") + 1
    print(f"      ✅ Berhasil tambah entri false positive -> total: {data_add2.get('total')}")

    resp_export = client.get("/api/dataset/export")
    assert resp_export.status_code == 200
    assert "attachment; filename=re_dataset_contributions.csv" in resp_export.headers.get("Content-Disposition", "")
    csv_text = resp_export.text
    lines = csv_text.strip().split("\n")
    expected_header = "Tweet,HS,Abusive,HS_Individual,HS_Group,HS_Religion,HS_Race,HS_Physical,HS_Gender,HS_Other,HS_Weak,HS_Moderate,HS_Strong"
    assert lines[0] == expected_header, f"Header CSV tidak sesuai! Didapat: {lines[0]}"
    assert len(lines) >= 3, f"Jumlah baris CSV tidak sesuai: {len(lines)}"
    assert any("oi babi,1,1,1,0,0,0,0,0,0,0,0,1" in line for line in lines)
    assert any("halo selamat pagi kawan-kawan semuanya,0,0,0,0,0,0,0,0,0,0,0,0" in line for line in lines)
    print("      ✅ CSV Header & Kolom cocok 100% dengan format re_dataset.csv (13 kolom).")

    # 6d. Uji Pencegahan Duplikasi (Cegah tambah berulang)
    resp_dup = client.post(
        "/api/dataset/add",
        json={
            "text": "oi babi",
            "labels": {"HS": 1},
            "source_log_id": 1,
        },
    )
    assert resp_dup.status_code == 409, f"Duplikasi tidak dicegah! Status: {resp_dup.status_code}"
    assert resp_dup.json().get("already_added") is True
    print("      ✅ Pencegahan duplikasi berhasil (HTTP 409: pesan yang sudah ada ditolak).")

    # 6e. Uji Tampilan Dataset & Hapus Entri Dataset
    print("[6e] Menguji API Tampilan Dataset (GET /api/dataset/list) & Hapus...")
    resp_list = client.get("/api/dataset/list")
    assert resp_list.status_code == 200, f"Gagal /api/dataset/list: {resp_list.status_code}"
    items = resp_list.json()
    assert len(items) >= 2, f"Jumlah data dataset kurang: {len(items)}"
    assert any(it["tweet"] == "oi babi" for it in items), "Entri 'oi babi' tidak ditemukan di dataset list"
    print(f"      ✅ Berhasil memuat {len(items)} entri di view tampilan dataset.")

    test_del_id = data_add1.get("id")
    resp_del = client.delete(f"/api/dataset/{test_del_id}")
    assert resp_del.status_code == 200, f"Gagal delete dataset: {resp_del.status_code}"
    print(f"      ✅ Berhasil menghapus entri dataset #{test_del_id}.")

    print("=" * 60)
    print("🎉 SEMUA PENGUJIAN SELESAI & BERHASIL 100%!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
