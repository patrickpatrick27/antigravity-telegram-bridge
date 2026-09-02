import os
import json
import html
import asyncio
import logging
from datetime import datetime
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from state import state

logger = logging.getLogger("antigravity-bridge.monitor")

def get_brain_dir() -> str:
    return os.path.expanduser("~/.gemini/antigravity-cli/brain")

def get_latest_milestones(conv_id: str = None, max_items: int = 3, min_timestamp: float = None) -> list[str]:
    brain_dir = get_brain_dir()
    if not conv_id and os.path.exists(brain_dir):
        dirs = [d for d in os.listdir(brain_dir) if len(d) == 36 and os.path.isdir(os.path.join(brain_dir, d))]
        if dirs:
            dirs.sort(key=lambda d: os.path.getmtime(os.path.join(brain_dir, d)), reverse=True)
            conv_id = dirs[0]

    if not conv_id:
        return []

    log_path = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        return []

    milestones = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines[-30:]):
                try:
                    data = json.loads(line.strip())
                    if min_timestamp and "created_at" in data:
                        try:
                            ca = data["created_at"]
                            dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                            if dt.timestamp() < min_timestamp:
                                continue
                        except Exception:
                            pass

                    if data.get("type") == "PLANNER_RESPONSE" and "tool_calls" in data:
                        for tc in data["tool_calls"]:
                            name = tc.get("name", "")
                            args = tc.get("args", {})
                            summary = args.get("toolSummary") or args.get("toolAction")
                            if summary:
                                summary = str(summary).strip('"').strip("'")
                            else:
                                if name == "run_command":
                                    cmd = str(args.get("CommandLine", "")).strip('"')
                                    summary = f"Run command: {cmd[:30]}..." if cmd else "Run command"
                                elif name == "view_file":
                                    path = str(args.get("AbsolutePath", "")).strip('"')
                                    summary = f"View {os.path.basename(path)}" if path else "View file"
                                elif name == "replace_file_content" or name == "write_to_file":
                                    path = str(args.get("TargetFile", "")).strip('"')
                                    summary = f"Edit {os.path.basename(path)}" if path else "Edit file"
                                else:
                                    summary = name.replace("_", " ").title()

                            icon = "⚡" if name == "run_command" else "📝" if ("file" in name or "edit" in name) else "🔍"
                            entry = f"{icon} <i>{html.escape(summary)}</i>"
                            if entry not in milestones:
                                milestones.append(entry)
                                if len(milestones) >= max_items:
                                    break
                        if len(milestones) >= max_items:
                            break
                except Exception:
                    continue
    except Exception:
        pass

    return list(reversed(milestones))

async def monitor_progress(chat_id: int, context: ContextTypes.DEFAULT_TYPE, stop_event: asyncio.Event, target_conv_id: str, start_time: float, holder: dict, min_timestamp: float = None):
    last_text = ""
    try:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            return
        except asyncio.TimeoutError:
            pass

        if stop_event.is_set():
            return

        status_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⏳ <i>Analyzing request and executing plan... (4s)</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        holder["status_msg"] = status_msg

        elapsed = 4
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3.0)
                break
            except asyncio.TimeoutError:
                pass

            if stop_event.is_set():
                break

            elapsed = int(asyncio.get_event_loop().time() - start_time)
            active_conv = state.get("current_session_id") or target_conv_id
            milestones = get_latest_milestones(active_conv, max_items=3, min_timestamp=min_timestamp)

            status_lines = [f"⏳ <b>Agent at work... ({elapsed}s)</b>"]
            if milestones:
                status_lines.append("")
                status_lines.extend(milestones)
            else:
                status_lines.append("<i>Reasoning and executing tool plan...</i>")

            new_text = "\n".join(status_lines)
            if new_text != last_text and holder.get("status_msg"):
                try:
                    await holder["status_msg"].edit_text(
                        new_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    last_text = new_text
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.debug(f"Progress update skipped: {e}")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Progress monitor notice: {e}")

async def send_typing_periodically(chat_id: int, context: ContextTypes.DEFAULT_TYPE, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

def get_session_stats(conv_id: str) -> dict:
    if not conv_id:
        return {"turns": 0, "steps": 0, "compressed": False}
    brain_dir = get_brain_dir()
    log_path = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        return {"turns": 0, "steps": 0, "compressed": False}
    turns = 0
    steps = 0
    has_compression = False
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                steps += 1
                if '"type":"USER_INPUT"' in line or '"type": "USER_INPUT"' in line:
                    turns += 1
                if '<CONTEXT_SUMMARY>' in line:
                    has_compression = True
    except Exception:
        pass
    return {"turns": turns, "steps": steps, "compressed": has_compression}

def get_turn_error(conv_id: str = None, min_timestamp: float = None) -> str | None:
    if not conv_id:
        return None
    brain_dir = get_brain_dir()
    log_path = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                try:
                    step = json.loads(line.strip())
                    if min_timestamp and "created_at" in step:
                        ca = step["created_at"]
                        dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                        if dt.timestamp() < min_timestamp:
                            break
                    if step.get("type") == "ERROR_MESSAGE" or (step.get("status") == "ERROR" and step.get("source") == "SYSTEM"):
                        content = step.get("content", "").strip()
                        if content:
                            return content
                except Exception:
                    continue
    except Exception:
        pass
    return None
