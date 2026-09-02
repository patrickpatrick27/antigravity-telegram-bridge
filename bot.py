#!/usr/bin/env python3
import asyncio
import logging
from telegram import BotCommand
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from handlers import (
    start_cmd,
    stop_cmd,
    cd_cmd,
    pwd_cmd,
    new_cmd,
    model_cmd,
    switch_shortcut_cmd,
    stats_cmd,
    context_cmd,
    handle_message,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("antigravity-bridge")

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("model", "View or switch active model"),
        BotCommand("gemini", "Switch to Gemini 3.7 Flash (Medium)"),
        BotCommand("gemini_medium", "Switch to Gemini 3.7 Flash (Medium)"),
        BotCommand("gemini_high", "Switch to Gemini 3.7 Flash (High)"),
        BotCommand("gemini_low", "Switch to Gemini 3.7 Flash (Low)"),
        BotCommand("claude", "Switch to Claude Sonnet 4.6 (Thinking)"),
        BotCommand("opus", "Switch to Claude Opus 4.6 (Thinking)"),
        BotCommand("pro", "Switch to Gemini 3.1 Pro (High)"),
        BotCommand("gpt", "Switch to GPT-OSS 120B (Medium)"),
        BotCommand("stats", "View model burn & token telemetry"),
        BotCommand("context", "View turn count & compression state"),
        BotCommand("cd", "Switch workspace directory"),
        BotCommand("pwd", "Show current workspace"),
        BotCommand("new", "Start fresh conversation session"),
        BotCommand("stop", "Abort currently running task"),
    ])

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Please configure .env file.")
        return

    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=60.0,
        write_timeout=60.0,
        media_write_timeout=120.0,
    )
    app = ApplicationBuilder().token(BOT_TOKEN).request(request).post_init(post_init).build()

    # General commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("abort", stop_cmd))
    app.add_handler(CommandHandler("cancel", stop_cmd))
    app.add_handler(CommandHandler("cd", cd_cmd))
    app.add_handler(CommandHandler("pwd", pwd_cmd))
    app.add_handler(CommandHandler("new", new_cmd))
    app.add_handler(CommandHandler("reset", new_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("burn", stats_cmd))
    app.add_handler(CommandHandler("context", context_cmd))
    app.add_handler(CommandHandler("session", context_cmd))

    # Model switching shortcuts
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("models", model_cmd))
    app.add_handler(CommandHandler("claude", lambda u, c: switch_shortcut_cmd(u, c, "claude")))
    app.add_handler(CommandHandler("sonnet", lambda u, c: switch_shortcut_cmd(u, c, "sonnet")))
    app.add_handler(CommandHandler("opus", lambda u, c: switch_shortcut_cmd(u, c, "opus")))
    app.add_handler(CommandHandler("gemini", lambda u, c: switch_shortcut_cmd(u, c, "gemini")))
    app.add_handler(CommandHandler("flash", lambda u, c: switch_shortcut_cmd(u, c, "flash")))
    app.add_handler(CommandHandler("gemini_medium", lambda u, c: switch_shortcut_cmd(u, c, "gemini-medium")))
    app.add_handler(CommandHandler("gemini_high", lambda u, c: switch_shortcut_cmd(u, c, "gemini-high")))
    app.add_handler(CommandHandler("gemini_low", lambda u, c: switch_shortcut_cmd(u, c, "gemini-low")))
    app.add_handler(CommandHandler("pro", lambda u, c: switch_shortcut_cmd(u, c, "pro")))
    app.add_handler(CommandHandler("gpt", lambda u, c: switch_shortcut_cmd(u, c, "gpt")))

    # Text, Photo, Document & Voice Message Handler
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO) & ~filters.COMMAND,
        handle_message
    ))

    logger.info("Antigravity Telegram Bridge starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
