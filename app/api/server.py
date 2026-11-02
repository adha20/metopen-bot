from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.schemas import HealthResponse, PredictionRequest, PredictionResponse
from app.dashboard.routes import DASHBOARD_DIR, router as dashboard_router
from app.database.db import init_db
from app.engine.indobert_engine import IndoBERTModerationEngine

engine: IndoBERTModerationEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Menginisialisasi Model IndoBERT sekali saat server startup."""
    global engine
    init_db()
    print("[API] Memulai AI Inference Server...")
    try:
        engine = IndoBERTModerationEngine.get_instance()
        print("[API] IndoBERT Engine berhasil dimuat!")
    except Exception as e:
        print(f"[API ERROR] Gagal memuat engine saat startup: {e}")
    yield
    print("[API] Mematikan AI Inference Server...")


app = FastAPI(
    title="IndoBERT Cyberbullying & Hate Speech API",
    description="Microservice REST API untuk Moderasi Teks Otomatis Bahasa Indonesia berbasis IndoBERT Multi-Label.",
    version="1.0.0",
    lifespan=lifespan,
)

# Aktifkan CORS agar bisa dipanggil dari dashboard / frontend manapun
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    global engine
    device_str = str(engine.device) if engine else "unknown"
    return HealthResponse(
        status="healthy" if engine else "degraded",
        service="cyberbully-detector-api",
        device=device_str,
        model_loaded=engine is not None,
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Inference"])
async def predict_moderation(payload: PredictionRequest) -> PredictionResponse:
    global engine
    if engine is None:
        # Lazy fallback initialize jika lifespan belum selesai
        try:
            engine = IndoBERTModerationEngine.get_instance()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Model engine belum siap: {e}")

    result = engine.predict(payload.text)
    return PredictionResponse(**result.to_dict())


# Web Dashboard Human-in-the-Loop: halaman "/" + API "/api/..." + file statis
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")
