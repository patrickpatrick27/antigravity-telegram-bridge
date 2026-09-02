import os
import re
import json
import html
import asyncio
import logging
import subprocess
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    is_authorized,
    DEFAULT_WORKSPACE,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    MODEL_DISPLAY_NAMES,
    AGY_BIN,
    BASE_DIR,
)
from state import state, save_state
from formatter import send_chunked_message
from monitor import (
    monitor_progress,
    send_typing_periodically,
    get_session_stats,
    get_turn_error,
)
from executor import (
    detect_model_intent,
    cancel_current_execution,
    run_subprocess_agy,
    CHAT_LOCK,
    WAS_CANCELLED,
)
from telemetry import (
    record_turn_telemetry,
    build_stats_message,
    get_last_turn_telemetry,
)

logger = logging.getLogger("antigravity-bridge.handlers")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized access.")
        return

    cur_model = state.get("model", DEFAULT_MODEL)
    cur_label = MODEL_DISPLAY_NAMES.get(cur_model, cur_model)

    msg = (
        "🚀 <b>Antigravity Assistant Online</b>\n\n"
        f"🤖 <b>Active Model:</b> <code>{cur_label}</code>\n"
        f"📁 <b>Workspace:</b> <code>{state['cwd']}</code>\n\n"
        "<b>Model Switching:</b>\n"
        "• <code>/gemini</code> or <code>/gemini_medium</code> : Gemini 3.7 Flash (Medium)\n"
        "• <code>/gemini_high</code> or <code>/high</code> : Gemini 3.7 Flash (High)\n"
        "• <code>/gemini_low</code> or <code>/low</code> : Gemini 3.7 Flash (Low)\n"
        "• <code>/claude</code> / <code>/sonnet [prompt]</code> : Claude Sonnet 4.6 (Thinking)\n"
        "• <code>/opus [prompt]</code> : Claude Opus 4.6 (Thinking)\n"
        "• <code>/pro [prompt]</code> : Gemini 3.1 Pro (High)\n"
        "• <code>/gpt [prompt]</code> : GPT-OSS 120B (Medium)\n"
        "• <code>/model &lt;name&gt;</code> : Switch active model\n\n"
        "<b>General Commands:</b>\n"
        "• <code>/stats</code> : View model burn & token telemetry\n"
        "• <code>/context</code> : View turn count & compression state\n"
        "• <code>/cd &lt;path&gt;</code> : Switch directory\n"
        "• <code>/pwd</code> : Show current directory\n"
        "• <code>/new</code> : Start fresh session\n"
        "• <code>/stop</code> : Cancel running execution"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    cancel_current_execution()
    await update.message.reply_text("🛑 Execution cancelled and process tree killed.")

async def cd_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: <code>/cd &lt;path&gt;</code>", parse_mode="HTML")
        return
    target_path = os.path.expanduser(context.args[0])
    if os.path.isdir(target_path):
        state["cwd"] = os.path.abspath(target_path)
        save_state()
        await update.message.reply_text(f"📁 Workspace set to: <code>{state['cwd']}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ Directory does not exist: <code>{target_path}</code>", parse_mode="HTML")

async def pwd_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(f"📁 Current Workspace: <code>{state['cwd']}</code>", parse_mode="HTML")

async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    old_id = state.get("current_session_id")
    state["current_session_id"] = None
    save_state()
    msg = "🔄 <b>Session Reset:</b> Next prompt will begin a fresh conversation context."
    if old_id:
        msg += f"\n<i>Previous session ID: {old_id}</i>"
    await update.message.reply_text(msg, parse_mode="HTML")

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    if context.args:
        alias = context.args[0].lower()
        if alias in AVAILABLE_MODELS:
            m_id, disp_name = AVAILABLE_MODELS[alias]
            state["model"] = m_id
            save_state()
            await update.message.reply_text(f"✅ Switched active model to: <b>{disp_name}</b>\n<code>{m_id}</code>", parse_mode="HTML")
            return
        else:
            await update.message.reply_text(f"⚠️ Unknown model alias: <code>{alias}</code>\nAvailable: {', '.join(AVAILABLE_MODELS.keys())}", parse_mode="HTML")
            return

    cur_model = state.get("model", DEFAULT_MODEL)
    cur_label = MODEL_DISPLAY_NAMES.get(cur_model, cur_model)
    avail = "\n".join([f"• <code>{alias}</code> -> {name}" for alias, (mid, name) in sorted(AVAILABLE_MODELS.items())])
    await update.message.reply_text(f"🤖 <b>Current Model:</b> <code>{cur_label}</code>\n\n<b>Available Models:</b>\n{avail}", parse_mode="HTML")

async def switch_shortcut_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, alias: str):
    if not is_authorized(update.effective_user.id):
        return
    if alias in AVAILABLE_MODELS:
        m_id, disp_name = AVAILABLE_MODELS[alias]
        state["model"] = m_id
        save_state()
        if context.args:
            await handle_message(update, context, custom_prompt=" ".join(context.args))
        else:
            await update.message.reply_text(f"✅ Switched active model to: <b>{disp_name}</b>\n<code>{m_id}</code>", parse_mode="HTML")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    msg = build_stats_message()
    await update.message.reply_text(msg, parse_mode="HTML")

async def context_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    conv_id = state.get("current_session_id")
    if not conv_id:
        await update.message.reply_text("📋 <b>Context Info:</b> No active conversation session (fresh start).", parse_mode="HTML")
        return
    stats = get_session_stats(conv_id)
    comp_badge = "🟢 Yes (Optimized)" if stats["compressed"] else "⚪ No (Full Transcript)"
    msg = (
        "📋 <b>Context & Session State:</b>\n\n"
        f"• <b>Session ID:</b> <code>{conv_id}</code>\n"
        f"• <b>Total User Turns:</b> <code>{stats['turns']}</code>\n"
        f"• <b>Total Planner Steps:</b> <code>{stats['steps']}</code>\n"
        f"• <b>Context Compression:</b> {comp_badge}\n\n"
        "<i>Tip: If sessions get too long, send /new to refresh token context.</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_prompt: str = None):
    if not is_authorized(update.effective_user.id):
        return

    raw_prompt = ""
    downloads_dir = os.path.join(BASE_DIR, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    if custom_prompt:
        raw_prompt = custom_prompt
    elif update.message and update.message.text:
        raw_prompt = update.message.text
    elif update.message and update.message.photo:
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id, read_timeout=60.0)
            ts = int(datetime.now().timestamp())
            img_path = os.path.join(downloads_dir, f"photo_{ts}.jpg")
            await file.download_to_drive(custom_path=img_path, read_timeout=60.0)
            caption = update.message.caption or "Please view and analyze this image."
            raw_prompt = f"[Client attached image file: {img_path} | Use view_file on this path to inspect]\n\n{caption}"
        except Exception as e:
            logger.exception("Error downloading photo")
            await update.message.reply_text(f"⚠️ Failed to download photo: {str(e)}")
            return
    elif update.message and update.message.document:
        try:
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id, read_timeout=60.0)
            ts = int(datetime.now().timestamp())
            clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', doc.file_name or "file")
            doc_path = os.path.join(downloads_dir, f"{ts}_{clean_name}")
            await file.download_to_drive(custom_path=doc_path, read_timeout=60.0)
            caption = update.message.caption or "Please view and analyze this attached document/file."
            raw_prompt = f"[Client attached file: {doc_path} | Use view_file on this path to inspect]\n\n{caption}"
        except Exception as e:
            logger.exception("Error downloading document")
            await update.message.reply_text(f"⚠️ Failed to download file: {str(e)}")
            return
    elif update.message and (update.message.voice or update.message.audio):
        try:
            media = update.message.voice or update.message.audio
            file = await context.bot.get_file(media.file_id, read_timeout=60.0)
            ts = int(datetime.now().timestamp())
            ext = "ogg" if update.message.voice else (media.file_name.split(".")[-1] if hasattr(media, "file_name") and media.file_name and "." in media.file_name else "mp3")
            audio_path = os.path.join(downloads_dir, f"voice_{ts}.{ext}")
            await file.download_to_drive(custom_path=audio_path, read_timeout=60.0)
            caption = update.message.caption or ""
            raw_prompt = f"[Client attached voice/audio file: {audio_path} | Use view_file on this path to listen and extract info]\n\n{caption or 'Please listen to this voice message, transcribe or extract the information, and answer accordingly.'}"
        except Exception as e:
            logger.exception("Error downloading voice/audio file")
            await update.message.reply_text(f"⚠️ Failed to download voice message: {str(e)}")
            return

    if not raw_prompt:
        return

    # Check for direct slash command aliases
    first_token = raw_prompt.split()[0].lower() if raw_prompt else ""
    if first_token.startswith("/"):
        cmd_candidate = first_token[1:]
        if cmd_candidate in AVAILABLE_MODELS:
            m_id, disp_name = AVAILABLE_MODELS[cmd_candidate]
            state["model"] = m_id
            save_state()
            rest_tokens = raw_prompt.split()[1:]
            if not rest_tokens:
                await update.message.reply_text(f"✅ Switched active model to: <b>{disp_name}</b>\n<code>{m_id}</code>", parse_mode="HTML")
                return
            raw_prompt = " ".join(rest_tokens)

    # Check for natural language model intent
    detected_model_id, detected_display_name, remaining_prompt = detect_model_intent(raw_prompt)
    if detected_model_id:
        state["model"] = detected_model_id
        save_state()
        raw_prompt = remaining_prompt
        if not raw_prompt or len(raw_prompt) < 2:
            await update.message.reply_text(f"✅ Switched active model to: <b>{detected_display_name}</b>\n<code>{detected_model_id}</code>", parse_mode="HTML")
            return

    if not raw_prompt:
        return

    async with CHAT_LOCK:
        chat_id = update.effective_chat.id
        stop_event = asyncio.Event()
        holder = {"status_msg": None}
        typing_task = asyncio.create_task(send_typing_periodically(chat_id, context, stop_event))
        start_time = asyncio.get_event_loop().time()
        query_start_epoch = datetime.now(timezone.utc).timestamp()
        monitor_task = asyncio.create_task(
            monitor_progress(
                chat_id,
                context,
                stop_event,
                state.get("current_session_id"),
                start_time,
                holder,
                min_timestamp=query_start_epoch
            )
        )

        try:
            telegram_context = "[Client: Telegram Mobile | Note: User is chatting via Telegram without physical terminal hotkeys (Ctrl+C) or IDE buttons. Commands are sent via chat / slash commands.]\n\n"
            effective_prompt = f"{telegram_context}{raw_prompt}"
            active_model = state.get("model", DEFAULT_MODEL)

            cmd = [
                AGY_BIN if os.path.exists(AGY_BIN) else "agy",
                "-p", effective_prompt,
                "--model", active_model,
                "--output-format", "json",
                "--print-timeout", "15m",
                "--dangerously-skip-permissions",
            ]

            if state.get("current_session_id"):
                cmd.extend(["--conversation", state["current_session_id"]])

            cwd = state["cwd"] if os.path.exists(state["cwd"]) else DEFAULT_WORKSPACE

            loop = asyncio.get_running_loop()
            returncode, stdout, stderr = await loop.run_in_executor(
                None, run_subprocess_agy, cmd, cwd, 900
            )

            response_text = ""
            data = None
            if stdout and stdout.strip():
                try:
                    parsed = json.loads(stdout.strip())
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    pass

                if not data:
                    m = re.search(r'(\{"conversation_id"[\s\S]*\})', stdout)
                    if m:
                        try:
                            parsed = json.loads(m.group(1))
                            if isinstance(parsed, dict):
                                data = parsed
                        except Exception:
                            pass

                if data:
                    if data.get("conversation_id"):
                        state["current_session_id"] = data["conversation_id"]
                        save_state()

                    conv_id = data.get("conversation_id") or state.get("current_session_id")
                    usage = data.get("usage") or {}
                    dur = data.get("duration_seconds", 0.0)
                    record_turn_telemetry(active_model, usage, dur, conv_id)
                    resp = (data.get("response") or "").strip()
                    turn_err = get_turn_error(conv_id, min_timestamp=query_start_epoch - 2.0)

                    if resp:
                        if turn_err:
                            response_text = f"{resp}\n\n⚠️ *(Note: The stream encountered an interruption: {turn_err}. You can continue or use /new if needed.)*"
                        else:
                            response_text = resp
                    elif turn_err:
                        is_timeout = "timeout" in turn_err.lower()
                        if is_timeout and state.get("current_session_id"):
                            state["current_session_id"] = None
                            save_state()
                            response_text = f"⚠️ **Antigravity Timeout / Error:**\n```\n{turn_err}\n```\n\n*(Session context was automatically reset to prevent repeated timeouts on your next message.)*"
                        else:
                            response_text = f"⚠️ **Antigravity Timeout / Error:**\n```\n{turn_err}\n```\n\n*Tip: Use /new to refresh conversation context if sessions get very large.*"
                    elif data.get("status") == "ERROR" or data.get("error"):
                        err_msg = data.get("error") or "Unknown error"
                        is_timeout = "timeout" in err_msg.lower()
                        if is_timeout and state.get("current_session_id"):
                            state["current_session_id"] = None
                            save_state()
                        response_text = f"⚠️ **Antigravity Timeout / Error:**\n```\n{err_msg}\n```\n\n*Tip: Use /new to refresh conversation context if sessions get very large.*"
                    else:
                        response_text = "*(Done with no textual output)*"

            if not response_text:
                if not data and stderr.strip():
                    if state.get("current_session_id"):
                        state["current_session_id"] = None
                        save_state()
                    response_text = f"⚠️ **Execution Error:**\n```\n{stderr.strip()}\n```\n\n*(Session state was reset so your next prompt starts clean.)*"
                elif stdout.strip() and not data:
                    response_text = stdout.strip()
                else:
                    response_text = "(Empty response from Antigravity)"

            stop_event.set()
            try:
                await monitor_task
            except Exception:
                pass

            await send_chunked_message(update, response_text, status_msg=holder.get("status_msg"))

        except asyncio.CancelledError:
            pass
        except subprocess.TimeoutExpired:
            if state.get("current_session_id"):
                state["current_session_id"] = None
                save_state()
            await update.message.reply_text("⏱️ Antigravity command timed out (15m limit). Session reset. You can retry with /new or re-send your message.")
        except Exception as e:
            if not WAS_CANCELLED:
                logger.exception("Error executing prompt")
                await update.message.reply_text(f"⚠️ Error: {str(e)}")
