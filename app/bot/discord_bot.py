from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import tasks

from app.bot.message_handler import handle_incoming_message
from app.config import settings
from app.database.db import fetch_due_temp_bans, mark_temp_ban_done


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = discord.Client(intents=intents)


@tasks.loop(seconds=30)
async def unban_expired() -> None:
    """Cabut ban sementara yang masa berlakunya sudah habis (tahan restart karena disimpan di DB)."""
    for ban in fetch_due_temp_bans(datetime.now(timezone.utc)):
        guild = bot.get_guild(int(ban["guild_id"]))
        if not guild:
            continue
        try:
            await guild.unban(discord.Object(id=int(ban["user_id"])), reason="Ban sementara berakhir")
        except discord.NotFound:
            pass  # sudah di-unban manual
        except discord.HTTPException as err:
            print(f"[Bot Warning] Gagal unban {ban['user_id']}: {err}")
            continue
        mark_temp_ban_done(ban["id"])


@bot.event
async def on_ready() -> None:
    bot_user = bot.user.name if bot.user else "unknown"
    print(f"[BOT] Logged in as {bot_user}")
    if not unban_expired.is_running():
        unban_expired.start()


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if settings.discord_guild_id and message.guild and message.guild.id != settings.discord_guild_id:
        return

    if (
        settings.discord_allowed_channel_ids
        and message.channel.id not in settings.discord_allowed_channel_ids
    ):
        return

    await handle_incoming_message(message)


def run_discord_bot() -> None:
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN belum diisi di file .env")

    bot.run(settings.discord_bot_token)
