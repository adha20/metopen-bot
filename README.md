# IndoBERT Multi-Label Cyberbullying & Hate Speech Detector (Discord Human-in-the-Loop)

Sistem moderasi teks otomatis *real-time* berbasis Deep Learning **IndoBERT Multi-Label** yang terintegrasi dengan **Discord Bot**, **FastAPI** (API inferensi + Web Dashboard Human-in-the-Loop dalam satu server).

Proyek ini dibangun untuk mendeteksi ujaran kebencian (*hate speech*) dan ujaran kasar (*abusive language*) dalam bahasa Indonesia ke dalam **12 kategori label spesifik**, sekaligus menyaring dan menghapus pesan dalam hitungan milidetik (< 300 ms) sebelum dibaca korban.

---

## 🏛️ Arsitektur Sistem (3-Tier Microservice)

```
[ Discord Gateway ] 
       ↕ (WebSocket)
[ Discord Bot Client ] ---> (1) Auto-Delete Pesan Melanggar (< 1s)
       ↕ (HTTP async)        (2) Kirim Alert Embed ke #admin-log
[ FastAPI (:8000): /predict + Web Dashboard ]
       ↕
[ IndoBERT Engine + Dynamic Thresholds ]
       ↕
[ SQLite Database (app.db) ] <--- [ Web Dashboard (/) ] <--- [ Admin Manusia (Human-in-the-Loop) ]
```

1. **Messaging Tier (Discord Bot):** Menyadap chat, mengekstrak mention korban (`@Adit` -> `[USER]`), menghapus pesan melanggar secara instan, dan menerbitkan tiket insiden ke channel `#admin-log`.
2. **AI Inference Microservice (FastAPI):** Menyajikan endpoint REST API `/predict` dengan latensi rendah (~200 ms) dan dokumentasi interaktif Swagger UI (`/docs`).
3. **Audit & Review Tier (Dashboard FastAPI & SQLite):** Mencatat seluruh riwayat pesan, kategori pelanggaran, rekam jejak pelaku, dan menyediakan dashboard pemantauan untuk admin manusia.

---

### 12 Kategori Label yang Dideteksi:
1. `HS`: Hate Speech (Ujaran Kebencian Umum)
2. `Abusive`: Kata Kasar / Makian
3. `HS_Individual`: Serangan Personal / Bullying Individu
4. `HS_Group`: Serangan terhadap Kelompok
5. `HS_Religion`: Ujaran Kebencian Agama
6. `HS_Race`: Ujaran Kebencian Ras / Etnis
7. `HS_Physical`: Ejekan Fisik / Disabilitas (*Body Shaming*)
8. `HS_Gender`: Diskriminasi Gender / Orientasi Seksual
9. `HS_Other`: Ujaran Kebencian Kategori Lain
10. `HS_Weak`: Tingkat Kebencian Ringan
11. `HS_Moderate`: Tingkat Kebencian Sedang
12. `HS_Strong`: Tingkat Kebencian Kuat / Berat

---

## 📁 Struktur Direktori

```text
cyberbully-discord-detector/
├── app/
│   ├── api/                      # FastAPI Microservice (/predict, /health)
│   │   ├── schemas.py
│   │   └── server.py
│   ├── bot/                      # Discord Bot Gateway & Message Handler
│   │   ├── discord_bot.py
│   │   └── message_handler.py
│   ├── dashboard/                # Web Dashboard (FastAPI + Jinja2)
│   │   ├── routes.py
│   │   └── templates/
│   ├── database/                 # SQLite ORM & Query Audit
│   │   └── db.py
│   ├── engine/                   # IndoBERT Model Engine & Preprocessing
│   │   └── indobert_engine.py
│   └── config.py                 # Konfigurasi Terpusat (.env)
├── data/
│   ├── dataset_raw/              # Kamus alay & dataset mentah
│   └── model/                    # Folder bobot model & threshold
│       ├── best_model_indobert.pt (Letakkan di sini)
│       └── optimal_thresholds_final.json
├── notebooks/                    # Jupyter Notebook Eksplorasi & Training
├── run.py                        # Entry-point runner terpadu
├── requirements.txt
└── .env.example
```

---

## 🚀 Panduan Instalasi & Menjalankan Proyek

### 1. Clone Repository
```bash
git clone https://github.com/adha20/metopen-bot.git
cd metopen-bot
```

### 2. Siapkan Python Virtual Environment
```bash
python -m venv .venv

# Di Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Di Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Siapkan File Konfigurasi `.env`
Salin template konfigurasi:
```bash
cp .env.example .env
```
Buka `.env` dan sesuaikan nilainya:
```env
DISCORD_BOT_TOKEN=token_bot_discord_anda
DISCORD_ADMIN_LOG_CHANNEL_ID=id_channel_khusus_admin_log
API_HOST=127.0.0.1
API_PORT=8000
API_URL=http://127.0.0.1:8000
RUN_MODE=all
KICK_VIOLATION_THRESHOLD=3
```

> **Penting di Discord Developer Portal:**  
> Pastikan opsi **`MESSAGE CONTENT INTENT`** dan **`SERVER MEMBERS INTENT`** di menu **Bot** sudah diaktifkan (*Checked*).

### 5. Masukkan File Bobot Model
Pastikan file bobot `best_model_indobert.pt` sudah diletakkan di dalam folder `data/model/`:
```text
data/model/best_model_indobert.pt
data/model/optimal_thresholds_final.json
```

### 6. Jalankan Sistem
Jalankan seluruh layanan (FastAPI + Dashboard + Bot Discord) dengan satu perintah:
```bash
python run.py --mode all
```

* **Swagger UI / API Docs:** Buka browser di [http://localhost:8000/docs](http://localhost:8000/docs)
* **Web Dashboard Admin:** Buka browser di [http://localhost:8000](http://localhost:8000)
* **Bot Discord:** Otomatis online di server Discord Anda.

---

## 🛠️ Opsi Mode Menjalankan Layanan Secara Terpisah

Jika Anda ingin menjalankan layanan secara independen:
* **Hanya API + Dashboard (tanpa bot):**
  ```bash
  python run.py --mode api
  ```
* **Hanya Bot Discord:**
  ```bash
  python run.py --mode bot
  ```

---

## 📄 Lisensi & Sitasi
Dataset ini menggunakan korpus dari penelitian:
> Muhammad Okky Ibrohim and Indra Budi. 2019. *Multi-label Hate Speech and Abusive Language Detection in Indonesian Twitter*. In Proceedings of the Third Workshop on Abusive Language Online (ALW3), pages 46–57, Florence, Italy. Association for Computational Linguistics.
