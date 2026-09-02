import os
import json
import logging
from config import STATE_FILE, DEFAULT_WORKSPACE, DEFAULT_MODEL

logger = logging.getLogger("antigravity-bridge.state")

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "cwd": data.get("cwd", DEFAULT_WORKSPACE),
                    "pinned_message_id": data.get("pinned_message_id"),
                    "pinned_chat_id": data.get("pinned_chat_id"),
                    "current_session_id": data.get("current_session_id"),
                    "model": data.get("model", DEFAULT_MODEL),
                }
        except Exception as e:
            logger.error(f"Error reading state file: {e}")
    return {
        "cwd": DEFAULT_WORKSPACE,
        "pinned_message_id": None,
        "pinned_chat_id": None,
        "current_session_id": None,
        "model": DEFAULT_MODEL,
    }

state = load_state()

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state file: {e}")
