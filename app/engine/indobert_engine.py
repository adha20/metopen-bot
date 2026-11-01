from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.config import settings

LABEL_COLUMNS = [
    "HS",
    "Abusive",
    "HS_Individual",
    "HS_Group",
    "HS_Religion",
    "HS_Race",
    "HS_Physical",
    "HS_Gender",
    "HS_Other",
    "HS_Weak",
    "HS_Moderate",
    "HS_Strong",
]

MODEL_NAME = "indobenchmark/indobert-base-p1"
MAX_LENGTH = 128


def _load_kamusalay_dict(csv_path: Path) -> dict[str, str]:
    """Memuat kamus kata alay / slang normalization."""
    mapping: dict[str, str] = {}
    if not csv_path.exists():
        return mapping

    try:
        import pandas as pd
        df = pd.read_csv(csv_path, encoding="latin-1", header=None)
        for _, row in df.iterrows():
            if pd.notna(row[0]) and pd.notna(row[1]):
                mapping[str(row[0]).strip().lower()] = str(row[1]).strip().lower()
    except Exception as e:
        print(f"[Warning] Gagal memuat kamus alay dari {csv_path}: {e}")
    return mapping


@dataclass
class ModerationResult:
    raw_text: str
    cleaned_text: str
    latency_ms: float
    is_violation: bool
    severity: str
    action: str
    strike_points: int
    violation_category: str
    victim_mentions: list[str]
    active_labels: list[str]
    probabilities: dict[str, float]
    thresholds: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "cleaned_text": self.cleaned_text,
            "latency_ms": round(self.latency_ms, 2),
            "is_violation": self.is_violation,
            "severity": self.severity,
            "action": self.action,
            "strike_points": self.strike_points,
            "violation_category": self.violation_category,
            "victim_mentions": self.victim_mentions,
            "active_labels": self.active_labels,
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "thresholds": {k: round(v, 2) for k, v in self.thresholds.items()},
        }


class IndoBERTModerationEngine:
    """Singleton Engine IndoBERT untuk Multi-Label Moderasi Teks Real-Time."""

    _instance: IndoBERTModerationEngine | None = None

    def __init__(
        self,
        model_path: Path | None = None,
        thresholds_path: Path | None = None,
        kamusalay_path: Path | None = None,
        device: str | None = None,
    ) -> None:
        self.model_path = model_path or settings.model_weights_path
        self.thresholds_path = thresholds_path or settings.thresholds_path
        self.kamusalay_path = kamusalay_path or settings.kamusalay_path

        # Pilih Device (GPU jika ada, jika tidak fallback ke CPU)
        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        print(f"[Engine] Menginisialisasi IndoBERT Moderation Engine pada device: {self.device}")

        # 1. Muat Kamus Alay
        self.kamusalay = _load_kamusalay_dict(self.kamusalay_path)
        print(f"[Engine] Kamus Alay termuat: {len(self.kamusalay)} entri kata.")

        # 2. Muat Tokenizer
        print(f"[Engine] Memuat Tokenizer ({MODEL_NAME})...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        # 3. Muat Threshold Optimal
        self.thresholds = self._load_thresholds()

        # 4. Muat Model
        self.model = self._load_model()
        self.model.eval()
        print("[Engine] Model IndoBERT siap melayani inferensi!")

    @classmethod
    def get_instance(cls) -> IndoBERTModerationEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_thresholds(self) -> dict[str, float]:
        default_thresh = {col: 0.50 for col in LABEL_COLUMNS}
        if self.thresholds_path and self.thresholds_path.exists():
            try:
                with open(self.thresholds_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for col in LABEL_COLUMNS:
                        if col in loaded:
                            default_thresh[col] = float(loaded[col])
                print(f"[Engine] Thresholds optimal berhasil dimuat dari {self.thresholds_path}")
            except Exception as e:
                print(f"[Warning] Gagal membaca file threshold, menggunakan default 0.5: {e}")
        else:
            print("[Info] File threshold optimal belum ditemukan, menggunakan default 0.5.")
        return default_thresh

    def _load_model(self) -> AutoModelForSequenceClassification:
        # Cek path utama atau nama alternatif (termasuk jika file berada di root repo)
        candidate_paths = [
            self.model_path,
            settings.model_dir / "best_model_indobert.pt",
            settings.model_dir / "best_model_indobert_optimized.pt",
            settings.model_dir / "best_model_indobert .pt",
            settings.base_dir / "best_model_indobert .pt",
            settings.base_dir / "best_model_indobert.pt",
            settings.base_dir / "best_model_indobert_optimized.pt",
        ]
        target_path = next((p for p in candidate_paths if p and p.exists()), None)

        if target_path and target_path.exists():
            from transformers import AutoConfig
            config = AutoConfig.from_pretrained(
                MODEL_NAME,
                num_labels=len(LABEL_COLUMNS),
                problem_type="multi_label_classification",
            )
            model = AutoModelForSequenceClassification.from_config(config).to(self.device)
            try:
                state_dict = torch.load(target_path, map_location=self.device)
                model.load_state_dict(state_dict)
                print(f"[Engine] Bobot model berhasil dimuat dari: {target_path}")
            except Exception as e:
                print(f"[Warning] Gagal memuat bobot model dari {target_path}: {e}")
        else:
            model = AutoModelForSequenceClassification.from_pretrained(
                MODEL_NAME,
                num_labels=len(LABEL_COLUMNS),
                problem_type="multi_label_classification",
            ).to(self.device)
            print(f"[Info] Model weights tidak ditemukan di {self.model_path}. Model berjalan dengan bobot pretrained default.")

        return model

    def preprocess_text(self, text: str) -> tuple[str, list[str]]:
        """Membersihkan teks dan mengekstrak target mention sesuai flow diagram."""
        if not text:
            return "", []

        # 1. Ekstrak korban / target mention (<@123456> atau @username)
        # Pola Discord mention: <@!?[0-9]+>
        victim_mentions: list[str] = re.findall(r"<@!?([0-9]+)>", text)
        plain_mentions: list[str] = re.findall(r"@([a-zA-Z0-9_\.]+)", text)
        all_victims = list(set(victim_mentions + plain_mentions))

        # 2. Samarkan mention menjadi token [USER] (persis alur diagram sistem)
        cleaned = re.sub(r"<@!?([0-9]+)>", "[USER]", text)
        cleaned = re.sub(r"@([a-zA-Z0-9_\.]+)", "[USER]", cleaned)

        # 3. Samarkan URL menjadi token [URL]
        cleaned = re.sub(r"http\S+|www\.\S+", "[URL]", cleaned)

        # 4. Potong karakter elongasi berulang (contoh: begooolll -> begol)
        cleaned = re.sub(r"([a-zA-Z])\1{2,}", r"\1\1", cleaned)

        # 5. Case folding & bersihkan simbol aneh
        cleaned = cleaned.lower()
        cleaned = re.sub(r"[^a-zA-Z0-9\s\[\]]", " ", cleaned)

        # 6. Normalisasi kata slang / alay
        tokens = cleaned.split()
        normalized_tokens = [self.kamusalay.get(tok, tok) for tok in tokens]
        final_cleaned = " ".join(normalized_tokens).strip()

        return final_cleaned, all_victims

    def predict(self, text: str) -> ModerationResult:
        """Menjalankan inferensi IndoBERT multi-label dan memetakan keputusan moderasi."""
        start_time = time.time()

        cleaned_text, victim_mentions = self.preprocess_text(text)

        # Jika teks kosong setelah dibersihkan
        if not cleaned_text:
            return ModerationResult(
                raw_text=text,
                cleaned_text="",
                latency_ms=(time.time() - start_time) * 1000,
                is_violation=False,
                severity="NORMAL",
                action="AMAN",
                strike_points=0,
                violation_category="Tidak Ada Pelanggaran",
                victim_mentions=[],
                active_labels=[],
                probabilities={col: 0.0 for col in LABEL_COLUMNS},
                thresholds=self.thresholds,
            )

        # Tokenisasi
        inputs = self.tokenizer(
            cleaned_text,
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
        ).to(self.device)

        # Inferensi model
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.sigmoid(outputs.logits).squeeze().cpu().numpy()

        latency_ms = (time.time() - start_time) * 1000

        # Evaluasi terhadap ambang batas masing-masing label
        probabilities: dict[str, float] = {}
        active_labels: list[str] = []

        for idx, col in enumerate(LABEL_COLUMNS):
            p = float(probs[idx])
            probabilities[col] = p
            thresh = float(self.thresholds.get(col, 0.50))
            if p >= thresh:
                active_labels.append(col)

        # Pemetaan Keputusan Moderasi & Penegakan Kebijakan (Rule-Based Policy)
        is_hs = "HS" in active_labels
        is_abusive = "Abusive" in active_labels
        is_violation = is_hs or is_abusive

        severity = "NORMAL"
        action = "AMAN"
        strike_points = 0
        violation_category = "Aman"

        if not is_violation:
            severity = "NORMAL"
            action = "AMAN"
            strike_points = 0
            violation_category = "Aman"
        elif not is_hs and is_abusive:
            severity = "TOXIC_RINGAN"
            action = "HAPUS_PESAN_DAN_PERINGATAN"
            strike_points = 1
            violation_category = "Ujaran Kasar / Abusive"
        else:
            # Terindikasi Hate Speech / Cyberbullying
            if "HS_Strong" in active_labels:
                severity = "BERAT_STRONG"
                action = "HAPUS_PESAN_DAN_ALERT_ADMIN"
                strike_points = 3
                violation_category = "Ujaran Kebencian Tingkat Tinggi (Strong Hate)"
            elif "HS_Religion" in active_labels or "HS_Race" in active_labels:
                severity = "BERAT_SARA"
                action = "HAPUS_PESAN_DAN_ALERT_ADMIN"
                strike_points = 3
                violation_category = "Ujaran Kebencian SARA (Agama / Ras)"
            elif "HS_Individual" in active_labels:
                severity = "SEDANG_PERSONAL"
                action = "HAPUS_PESAN_DAN_ALERT_ADMIN"
                strike_points = 2
                violation_category = "Cyberbullying Personal (Individual Target)"
            elif "HS_Physical" in active_labels or "HS_Gender" in active_labels:
                severity = "SEDANG_DISKRIMINASI"
                action = "HAPUS_PESAN_DAN_ALERT_ADMIN"
                strike_points = 2
                violation_category = "Diskriminasi Fisik / Gender"
            else:
                severity = "SEDANG"
                action = "HAPUS_PESAN_DAN_PERINGATAN"
                strike_points = 1
                violation_category = "Ujaran Kebencian (Umum)"

        return ModerationResult(
            raw_text=text,
            cleaned_text=cleaned_text,
            latency_ms=latency_ms,
            is_violation=is_violation,
            severity=severity,
            action=action,
            strike_points=strike_points,
            violation_category=violation_category,
            victim_mentions=victim_mentions,
            active_labels=active_labels,
            probabilities=probabilities,
            thresholds=self.thresholds,
        )

