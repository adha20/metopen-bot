from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.bot.actions import DISCORD_ACTIONS, ActionError, run_discord_action, run_restore_message
from app.database.db import (
    apply_user_action,
    count_dataset_contributions,
    delete_analysis_log,
    execute_dashboard_review_action,
    export_dataset_contributions_csv,
    fetch_audit_logs,
    fetch_dashboard_stats,
    fetch_flagged_queue,
    fetch_label_distribution,
    fetch_log_by_id,
    fetch_log_context,
    fetch_user_context,
    fetch_users_summary,
    save_dataset_contribution,
    update_analysis_log,
)

DASHBOARD_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=DASHBOARD_DIR / "templates")

# Semua route memakai `def` biasa (bukan `async def`) karena SQLite bersifat blocking;
# FastAPI otomatis menjalankannya di thread pool sehingga request lain tidak tertahan.
router = APIRouter()

Action = Literal["pardon", "warn", "timeout_10m", "timeout_1h", "timeout_24h", "kick", "ban"]


class ReviewActionBody(BaseModel):
    message_id: str | int
    action: Action
    notes: str | None = None
    duration_minutes: int | None = None


class UserActionBody(BaseModel):
    user_id: str | int
    action: Action
    reason: str | None = None
    duration_minutes: int | None = None


class MessageUpdateBody(BaseModel):
    status: str = ""
    admin_notes: str | None = None


class DatasetAddBody(BaseModel):
    text: str = ""
    labels: dict[str, Any] = {}
    source_log_id: str | int | None = None


def _error(message: str, status_code: int, **extra: Any) -> JSONResponse:
    # Frontend (dashboard.js) membaca field "error"
    return JSONResponse({"error": message, **extra}, status_code=status_code)


def _parse_log_id(value: str | int) -> int:
    cleaned = str(value).replace("msg_", "")
    return int(cleaned) if cleaned.isdigit() else 0


def _positive_or_none(minutes: int | None) -> int | None:
    """Durasi ban dalam menit; kosong/0 berarti permanen."""
    return minutes if minutes and minutes > 0 else None


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stats": fetch_dashboard_stats(),
            "flagged": fetch_flagged_queue(),
            "audit_logs": fetch_audit_logs(),
            "label_dist": fetch_label_distribution(),
            "users_summary": fetch_users_summary(),
            "dataset_count": count_dataset_contributions(),
        },
    )


@router.get("/api/stats", tags=["Dashboard"])
def api_stats():
    return fetch_dashboard_stats()


@router.get("/api/flagged-queue", tags=["Dashboard"])
def api_flagged_queue():
    return fetch_flagged_queue()


@router.get("/api/audit-logs", tags=["Dashboard"])
def api_audit_logs(
    search: str | None = None,
    label_filter: str | None = None,
    status_filter: str | None = None,
):
    return fetch_audit_logs(search=search, label_filter=label_filter, status_filter=status_filter)


@router.get("/api/users-summary", tags=["Dashboard"])
def api_users_summary():
    return fetch_users_summary()


@router.get("/api/messages/{message_id}", tags=["Dashboard"])
def api_message_get(message_id: str):
    raw_id = _parse_log_id(message_id)
    if not raw_id:
        return _error("Invalid message ID", 400)
    msg = fetch_log_by_id(raw_id)
    return msg if msg else _error("Message not found", 404)


@router.put("/api/messages/{message_id}", tags=["Dashboard"])
def api_message_update(message_id: str, body: MessageUpdateBody):
    raw_id = _parse_log_id(message_id)
    if not raw_id:
        return _error("Invalid message ID", 400)
    updated = update_analysis_log(log_id=raw_id, status=body.status, admin_notes=body.admin_notes)
    return updated if updated else _error("Message not found", 404)


@router.delete("/api/messages/{message_id}", tags=["Dashboard"])
def api_message_delete(message_id: str):
    raw_id = _parse_log_id(message_id)
    if not raw_id:
        return _error("Invalid message ID", 400)
    if not delete_analysis_log(raw_id):
        return _error("Message not found", 404)
    return {"success": True, "message_id": message_id}


@router.post("/api/actions/review", tags=["Dashboard"])
def api_review_action(body: ReviewActionBody):
    raw_id = _parse_log_id(body.message_id)
    if not raw_id:
        return _error("Invalid message ID", 400)

    ctx = fetch_log_context(raw_id)
    if not ctx:
        return _error("Message not found", 404)

    action = body.action
    duration = _positive_or_none(body.duration_minutes)
    discord_message = ""

    if action in DISCORD_ACTIONS:
        try:
            discord_message = run_discord_action(
                action=action,
                user_id=ctx["user_id"],
                guild_id=ctx["guild_id"],
                channel_id=ctx["channel_id"],
                duration_minutes=duration,
                audit_reason=body.notes,
            )
        except ActionError as err:
            return _error(str(err), err.status_code)
    elif action == "pardon":
        # Discord tidak bisa meng-undelete pesan; bot mengirim ulang isinya.
        # Best-effort: gagal kirim ulang tidak menghalangi pardon.
        msg = fetch_log_by_id(raw_id)
        if msg and msg["automated_action"] == "Pesan Dihapus Otomatis (Sanitasi)":
            try:
                discord_message = run_restore_message(
                    guild_id=ctx["guild_id"],
                    channel_id=ctx["channel_id"],
                    author=msg["author"],
                    content=msg["content"],
                )
            except ActionError as err:
                discord_message = f"Status dipulihkan, tapi pesan tidak bisa dikirim ulang: {err}"

    result = execute_dashboard_review_action(raw_id, action, body.notes, duration)
    if not result:
        return _error("Message not found", 404)
    result["discord_message"] = discord_message
    return result


@router.post("/api/actions/user", tags=["Dashboard"])
def api_user_action(body: UserActionBody):
    user_id = str(body.user_id).strip()
    if not user_id.isdigit():
        return _error("ID pengguna tidak valid", 400)

    action = body.action
    reason = (body.reason or "").strip() or None
    duration = _positive_or_none(body.duration_minutes)
    discord_message = ""

    if action in DISCORD_ACTIONS:
        ctx = fetch_user_context(user_id)
        try:
            discord_message = run_discord_action(
                action=action,
                user_id=user_id,
                guild_id=ctx["guild_id"],
                channel_id=ctx["channel_id"],
                duration_minutes=duration,
                audit_reason=reason or "Sanksi manual oleh Administrator dashboard",
                dm_note=reason,
            )
        except ActionError as err:
            return _error(str(err), err.status_code)

    resolved = apply_user_action(user_id, action, reason, duration)
    return {"success": True, "resolved_messages": resolved, "discord_message": discord_message}


@router.post("/api/dataset/add", tags=["Dashboard"])
def api_dataset_add(body: DatasetAddBody):
    text = body.text.strip()
    if not text:
        return _error("Teks kalimat tidak boleh kosong", 400)

    source_id = body.source_log_id
    if isinstance(source_id, str):
        digits = "".join(ch for ch in source_id if ch.isdigit())
        source_id = int(digits) if digits else None

    try:
        row_id = save_dataset_contribution(text, body.labels, source_id)
    except ValueError as err:
        return _error(str(err), 409, already_added=True)

    return {
        "success": True,
        "id": row_id,
        "total": count_dataset_contributions(),
        "source_log_id": source_id,
    }


@router.get("/api/dataset/export", tags=["Dashboard"])
def api_dataset_export():
    return Response(
        export_dataset_contributions_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=re_dataset_contributions.csv"},
    )
