from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timedelta, timezone

import discord

from app.config import settings
from app.database.db import add_temp_ban, cancel_temp_bans
from app.utils.durations import format_duration

TIMEOUT_MINUTES = {"timeout_10m": 10, "timeout_1h": 60, "timeout_24h": 1440}
DISCORD_ACTIONS = {"warn", "kick", "ban", *TIMEOUT_MINUTES}


class ActionError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _resolve_guild(client: discord.Client, guild_id: str) -> discord.Guild:
    for candidate in (guild_id, settings.discord_guild_id):
        try:
            guild = client.get_guild(int(candidate)) if candidate else None
        except ValueError:
            guild = None
        if guild:
            return guild
    if len(client.guilds) == 1:
        return client.guilds[0]
    raise ActionError("Server Discord tidak ditemukan oleh bot.", 404)


def _explain_forbidden(guild: discord.Guild, uid: int, action: str) -> str:
    """Jelaskan penyebab Forbidden yang paling mungkin, bukan sekadar 'tidak punya izin'."""
    if guild.owner_id == uid:
        return "Pengguna ini adalah OWNER server. Discord tidak mengizinkan siapa pun, termasuk bot, men-timeout/kick/ban owner. Coba dengan akun non-owner."

    perm_attr, perm_name = {
        "kick": ("kick_members", "Kick Members"),
        "ban": ("ban_members", "Ban Members"),
    }.get(action, ("moderate_members", "Moderate Members"))
    me = guild.me
    if me and not getattr(me.guild_permissions, perm_attr):
        return f"Bot belum punya permission '{perm_name}'. Aktifkan di Server Settings > Roles > role bot."

    member = guild.get_member(uid)
    if member:
        if action in TIMEOUT_MINUTES and member.guild_permissions.administrator:
            return "Pengguna punya permission Administrator, dan Discord tidak mengizinkan timeout untuk admin."
        if me and member.top_role >= me.top_role:
            return "Role pengguna sama atau lebih tinggi dari role bot. Pindahkan role bot ke atas role pengguna di Server Settings > Roles."
    return "Discord menolak tindakan ini. Periksa permission bot dan posisi role bot."


async def _restore(client: discord.Client, guild_id: str, channel_id: str, author: str, content: str) -> str:
    guild = _resolve_guild(client, guild_id)
    channel = guild.get_channel(int(channel_id)) if channel_id.isdigit() else None
    if not isinstance(channel, discord.abc.Messageable):
        raise ActionError("Channel asal pesan tidak ditemukan.", 404)
    try:
        await channel.send(
            f"↩️ Pesan dari **{author}** dipulihkan oleh moderator:\n>>> {content}",
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.Forbidden:
        raise ActionError("Bot tidak punya izin mengirim pesan di channel asal.", 403)
    except discord.HTTPException as err:
        raise ActionError(f"Discord menolak permintaan: {err.text or err}", 502)
    return "Pesan dikirim ulang oleh bot di channel asal."


async def _warn(
    client: discord.Client,
    guild: discord.Guild,
    uid: int,
    channel_id: str,
    dm_note: str | None,
) -> str:
    text = (
        f"⚠️ **Peringatan dari moderator {guild.name}**\n"
        "Pesanmu terindikasi melanggar aturan server. Mohon jaga etika berkomunikasi."
    )
    if dm_note:
        text += f"\n\nCatatan moderator: {dm_note}"

    user = guild.get_member(uid) or await client.fetch_user(uid)
    try:
        await user.send(text)
        return "Peringatan terkirim lewat DM."
    except discord.Forbidden:
        channel = guild.get_channel(int(channel_id)) if channel_id.isdigit() else None
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(f"{user.mention} {text}")
            return "DM pengguna tertutup, peringatan dikirim di channel."
        raise ActionError("DM pengguna tertutup dan channel asal tidak ditemukan.", 409)


async def _ban(guild: discord.Guild, uid: int, duration_minutes: int | None, reason: str | None) -> str:
    await guild.ban(discord.Object(id=uid), reason=reason, delete_message_seconds=0)
    cancel_temp_bans(str(uid), str(guild.id))
    if duration_minutes:
        unban_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        add_temp_ban(str(uid), str(guild.id), unban_at)
    return f"Pengguna di-ban ({format_duration(duration_minutes)})."


async def _perform(
    client: discord.Client,
    *,
    action: str,
    user_id: str,
    guild_id: str,
    channel_id: str,
    duration_minutes: int | None,
    audit_reason: str | None,
    dm_note: str | None,
) -> str:
    if not user_id.isdigit():
        raise ActionError("ID pengguna tidak valid.", 400)
    uid = int(user_id)
    guild = _resolve_guild(client, guild_id)

    try:
        if action == "warn":
            return await _warn(client, guild, uid, channel_id, dm_note)
        if action == "ban":
            return await _ban(guild, uid, duration_minutes, audit_reason)

        member = guild.get_member(uid) or await guild.fetch_member(uid)
        if action in TIMEOUT_MINUTES:
            await member.timeout(timedelta(minutes=TIMEOUT_MINUTES[action]), reason=audit_reason)
            return f"Pengguna di-timeout ({format_duration(TIMEOUT_MINUTES[action])})."
        await member.kick(reason=audit_reason)
        return "Pengguna di-kick dari server."
    except discord.Forbidden:
        raise ActionError(_explain_forbidden(guild, uid, action), 403)
    except discord.NotFound:
        raise ActionError("Pengguna tidak ditemukan di server (mungkin sudah keluar).", 404)
    except discord.HTTPException as err:
        raise ActionError(f"Discord menolak permintaan: {err.text or err}", 502)


def _run_on_bot(make_coro):
    """Dipanggil dari thread Flask: jalankan coroutine di event loop bot yang sedang hidup."""
    from app.bot.discord_bot import bot

    if not bot.is_ready():
        raise ActionError(
            "Bot Discord belum aktif. Jalankan dengan `python run.py` (mode all/bot) agar aksi bisa dieksekusi.",
            503,
        )

    future = asyncio.run_coroutine_threadsafe(make_coro(bot), bot.loop)
    try:
        return future.result(timeout=20)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise ActionError("Bot Discord tidak merespons (timeout).", 504)


def run_discord_action(
    *,
    action: str,
    user_id: str,
    guild_id: str = "",
    channel_id: str = "",
    duration_minutes: int | None = None,
    audit_reason: str | None = None,
    dm_note: str | None = None,
) -> str:
    return _run_on_bot(
        lambda bot: _perform(
            bot,
            action=action,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            duration_minutes=duration_minutes,
            audit_reason=audit_reason,
            dm_note=dm_note,
        )
    )


def run_restore_message(*, guild_id: str, channel_id: str, author: str, content: str) -> str:
    return _run_on_bot(lambda bot: _restore(bot, guild_id, channel_id, author, content))
