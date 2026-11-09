from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord import Forbidden, HTTPException, Member, Message, TextChannel

from app.config import settings
from app.database.db import record_user_violation, save_analysis_result
from app.dashboard.events import broadcaster
from app.utils.latency_log import log_latency


def _display_name(user) -> str:
    """Nama ramah-baca '@nama' dari Member/User (nick server > nama global > username)."""
    name = getattr(user, "display_name", None) or getattr(user, "name", None) or str(user)
    return name if name.startswith("@") else f"@{name}"


def _resolve_victims(message: Message, result: dict) -> list[str]:
    """Target dalam bentuk '@nama'. Mention asli diambil dari Discord; token angka tidak pernah ditampilkan."""
    names = [_display_name(m) for m in message.mentions if m.id != message.author.id]
    if not names:
        names = [f"@{t}" for t in (str(v).strip("<@!>") for v in result.get("victim_mentions", [])) if t and not t.isdigit()]
    return list(dict.fromkeys(names))


def _dataset_labels(result: dict) -> str:
    """Label terdeteksi persis seperti nama kolom dataset (HS, Abusive, HS_Individual, ...)."""
    return ", ".join(result.get("active_labels", [])) or "Tidak ada label"


async def _call_api_or_local(message: Message) -> dict:
    """Mengirim teks ke Microservice FastAPI, atau fallback ke engine lokal jika API offline."""
    payload = {
        "text": message.content,
        "author_id": str(message.author.id),
        "author_name": str(message.author.name),
        "channel_id": str(message.channel.id),
        "guild_id": str(message.guild.id) if message.guild else "",
    }

    # 1. Coba hubungi FastAPI Microservice via HTTP non-blocking
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.0)) as session:
            async with session.post(f"{settings.api_url}/predict", json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass  # FastAPI offline, beralih ke fallback lokal

    # 2. Fallback: Eksekusi in-memory langsung jika API service belum dinyalakan
    try:
        from app.engine.indobert_engine import IndoBERTModerationEngine
        engine = IndoBERTModerationEngine.get_instance()
        res = engine.predict(message.content)
        return res.to_dict()
    except Exception as e:
        print(f"[Bot Warning] Gagal menjalankan inferensi moderasi: {e}")
        return {
            "raw_text": message.content,
            "cleaned_text": message.content,
            "latency_ms": 0.0,
            "is_violation": False,
            "severity": "NORMAL",
            "action": "AMAN",
            "strike_points": 0,
            "violation_category": "Error Inferensi",
            "victim_mentions": [],
            "active_labels": [],
            "probabilities": {},
            "thresholds": {},
        }


async def _delete_message(message: Message) -> bool:
    try:
        await message.delete()
        return True
    except (Forbidden, HTTPException):
        return False


async def _kick_member(member: Member, reason: str) -> bool:
    try:
        await member.kick(reason=reason)
        return True
    except (Forbidden, HTTPException):
        return False


def _find_admin_log_channel(guild: discord.Guild) -> TextChannel | None:
    """Mencari channel admin log berdasarkan konfigurasi ID atau nama channel."""
    if settings.discord_admin_log_channel_id:
        ch = guild.get_channel(settings.discord_admin_log_channel_id)
        if isinstance(ch, TextChannel):
            return ch

    # Cari berdasarkan nama channel standar
    for name in ["admin-log", "laporan-admin", "moderasi-log", "mod-logs", "audit-log"]:
        for ch in guild.text_channels:
            if ch.name.lower() == name:
                return ch
    return None


async def _send_admin_alert_embed(
    message: Message,
    result: dict,
    total_violations: int,
    user_kicked: bool,
    author_name: str,
    victim_names: list[str],
    clean_text: str,
) -> None:
    """Mengirim tiket laporan Human-in-the-Loop ke channel admin."""
    if not message.guild:
        return

    admin_channel = _find_admin_log_channel(message.guild)
    if not admin_channel:
        return

    severity = result.get("severity", "SEDANG")

    color = discord.Color.red() if "BERAT" in severity else discord.Color.orange()

    embed = discord.Embed(
        title=f"🚨 [LAPORAN MODERASI] {_dataset_labels(result)}",
        description="Pesan melanggar terdeteksi otomatis oleh IndoBERT dan telah disanitasi.",
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    embed.add_field(
        name="👤 Pelaku",
        value=f"{author_name}\n(ID: `{message.author.id}`)",
        inline=True,
    )

    victim_text = ", ".join(victim_names) if victim_names else "*Tidak ada mention spesifik (Publik)*"

    embed.add_field(name="🎯 Target / Korban", value=victim_text, inline=True)
    embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)

    # Pesan Asli vs Teks yang Dinormalisasi
    embed.add_field(name="💬 Pesan Asli (Sebelum Dihapus)", value=f"```{clean_text}```", inline=False)
    embed.add_field(name="🧹 Teks AI (Normalized)", value=f"`{result.get('cleaned_text', '-')}`", inline=False)

    # Label & Probabilitas
    labels = result.get("active_labels", [])
    label_str = ", ".join([f"`{l}`" for l in labels]) if labels else "`None`"
    embed.add_field(name="🏷️ Label Terdeteksi", value=label_str, inline=True)

    probs = result.get("probabilities", {})
    top_prob = max(probs.values()) if probs else 0.0
    embed.add_field(name="📊 Keyakinan AI", value=f"`{top_prob * 100:.1f}%`", inline=True)
    embed.add_field(name="⚡ Latensi Inferensi", value=f"`{result.get('latency_ms', 0):.1f} ms`", inline=True)

    # Status Rekam Jejak (Berbasis Jumlah Pelanggaran Murni, Bukan Sistem Poin)
    status_text = f"Pelanggaran ke-`{total_violations}` | Total: `{total_violations}/{settings.kick_violation_threshold}` kali"
    if user_kicked:
        status_text += "\n⛔ **STATUS: USER TELAH DI-KICK DARI SERVER!**"
    elif total_violations >= settings.kick_violation_threshold:
        if message.guild and message.author.id == message.guild.owner_id:
            status_text += "\n⚠️ **STATUS: Pelaku adalah Pemilik Server (Discord tidak mengizinkan bot me-kick Server Owner).**"
        else:
            status_text += "\n⚠️ **STATUS: Bot gagal me-kick (periksa izin 'Kick Members' atau urutan role bot).**"

    embed.add_field(name="⚖️ Rekam Jejak Pelanggaran", value=status_text, inline=False)
    embed.set_footer(text="Human-in-the-Loop Moderation System | Powered by IndoBERT")

    try:
        await admin_channel.send(embed=embed)
    except Exception as e:
        print(f"[Bot Warning] Gagal mengirim alert embed ke admin: {e}")


async def handle_incoming_message(message: Message) -> None:
    t_start = time.perf_counter()  # awal pengukuran E2E: bot menerima pesan
    received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    # Abaikan pesan dari bot sendiri atau bot lain
    if message.author.bot:
        return

    # Filter channel jika diatur di konfigurasi
    if (
        settings.discord_allowed_channel_ids
        and message.channel.id not in settings.discord_allowed_channel_ids
    ):
        return

    # 1. Panggil Inferensi AI (FastAPI / Local Engine)
    t_infer = time.perf_counter()
    result = await _call_api_or_local(message)
    inference_ms = (time.perf_counter() - t_infer) * 1000

    is_violation = bool(result.get("is_violation", False))
    action_taken = str(result.get("action", "AMAN"))

    message_deleted = False
    user_kicked = False
    total_violations = 0
    e2e_ms: float | None = None
    admin_notify_ms: float | None = None

    # Resolusi nama sekali saja: dipakai embed admin, database, dan dashboard
    author_name = _display_name(message.author)
    victim_names = _resolve_victims(message, result)
    clean_text = message.clean_content

    # 2. Jika Terindikasi Pelanggaran -> Eksekusi Paralel (Sesuai Diagram)
    if is_violation:
        # Aksi 1: Hapus Pesan Real-Time di Channel (< 1 Detik)
        message_deleted = await _delete_message(message)

        # Catat 1 kali pelanggaran ke database (Bukan sistem poin, tapi jumlah pelanggaran murni)
        total_violations = record_user_violation(
            user_id=str(message.author.id),
            user_name=author_name,
        )
        # Akhir E2E (pelanggaran): pesan sudah dihapus & pelanggaran tercatat di SQLite.
        # Peringatan di channel (+ sleep), kick, dan notifikasi admin sengaja di luar pengukuran utama.
        e2e_ms = (time.perf_counter() - t_start) * 1000

        # Kirim Peringatan Ringan di Channel
        try:
            warn_msg = await message.channel.send(
                f"⚠️ {message.author.mention} Pesan Anda telah dihapus karena terindikasi **{_dataset_labels(result)}** "
                f"(Pelanggaran ke-{total_violations} dari batas {settings.kick_violation_threshold} kali)."
            )
            # Hapus pesan peringatan bot setelah beberapa detik agar chat tetap bersih
            await asyncio.sleep(settings.warning_delete_after_seconds)
            await warn_msg.delete()
        except Exception:
            pass

        # Cek Ambang Batas Jumlah Pelanggaran untuk Kick Otomatis
        if (
            message.guild
            and isinstance(message.author, Member)
            and total_violations >= settings.kick_violation_threshold
        ):
            user_kicked = await _kick_member(
                message.author,
                reason=f"Telah mencapai batas {total_violations} kali pelanggaran ujaran kebencian/kasar (HS/Abusive).",
            )
            if user_kicked:
                action_taken = "KICKED"
                try:
                    await message.channel.send(
                        f"⛔ {message.author.mention} telah dikeluarkan (kick) dari server karena telah mencapai "
                        f"{total_violations} kali pelanggaran."
                    )
                except Exception:
                    pass

        # Aksi 2: Kirim Laporan Audit Lengkap ke Admin (Human-in-the-Loop)
        t_admin = time.perf_counter()
        await _send_admin_alert_embed(
            message=message,
            result=result,
            total_violations=total_violations,
            user_kicked=user_kicked,
            author_name=author_name,
            victim_names=victim_names,
            clean_text=clean_text,
        )
        admin_notify_ms = (time.perf_counter() - t_admin) * 1000

    # Akhir E2E (aman): keputusan moderasi selesai, tidak ada tindakan yang perlu ditunggu.
    if e2e_ms is None:
        e2e_ms = (time.perf_counter() - t_start) * 1000

    # 3. Simpan Riwayat ke Database SQLite (Audit Trail)
    probs = result.get("probabilities", {})
    confidence = max(probs.values()) if probs else 0.0
    active_labels_str = ", ".join(result.get("active_labels", []))

    save_analysis_result(
        raw_content=clean_text,
        normalized_content=result.get("cleaned_text", ""),
        label=result.get("violation_category", "Aman"),
        user_id=str(message.author.id),
        user_name=author_name,
        channel_id=str(message.channel.id),
        channel_name=getattr(message.channel, "name", ""),
        guild_id=str(message.guild.id) if message.guild else "",
        guild_name=getattr(message.guild, "name", "") if message.guild else "",
        violation_points_added=1 if is_violation else 0,
        total_violation_points=total_violations,
        action_taken=action_taken,
        message_deleted=message_deleted,
        user_kicked=user_kicked,
        active_labels=active_labels_str,
        severity=result.get("severity", "NORMAL"),
        latency_ms=result.get("latency_ms", 0.0),
        victim_names=", ".join(victim_names),
        confidence_score=confidence,
    )

    if result.get("violation_category") == "Error Inferensi":
        status = "INFERENCE_ERROR"
    elif not is_violation:
        status = "SAFE"
    else:
        status = "VIOLATION_DELETED" if message_deleted else "VIOLATION_DELETE_FAILED"
    log_latency(
        {
            "timestamp": received_at,
            "message_id": message.id,
            "status": status,
            "inference_latency_ms": inference_ms,
            "e2e_latency_ms": e2e_ms,
            "model_latency_ms": result.get("latency_ms", 0.0),
            "admin_notify_ms": admin_notify_ms,
        }
    )

    try:
        broadcaster.broadcast(
            "new_message",
            {
                "is_violation": is_violation,
                "label": result.get("violation_category", "Aman"),
                "author": author_name,
            },
        )
    except Exception:
        pass
