import os
import re
import signal
import asyncio
import logging
import subprocess

from config import AVAILABLE_MODELS

logger = logging.getLogger("antigravity-bridge.executor")

CURRENT_PROCESS = None
CURRENT_TASK = None
WAS_CANCELLED = False
CHAT_LOCK = asyncio.Lock()

def detect_model_intent(prompt: str):
    p = prompt.strip()
    pattern = r'(?:\b(?:please\s+)?(?:switch\s+(?:model\s+)?to|use|run\s+(?:with|on)|using|with)\s+(claude|sonnet|opus|gemini|flash|pro|gpt|medium(?:\s+effort)?|high(?:\s+effort)?|gemini-medium|gemini-high|flash-medium|flash-high)\b)'
    m = re.search(pattern, p, flags=re.IGNORECASE)
    if m:
        matched_str = m.group(1).lower()
        alias = re.sub(r'\s+effort$', '', matched_str).strip()
        if alias in AVAILABLE_MODELS:
            model_id, display_name = AVAILABLE_MODELS[alias]
            cleaned = re.sub(pattern, '', p, count=1, flags=re.IGNORECASE).strip(' ,.:;-')
            return model_id, display_name, cleaned
    return None, None, prompt

def cancel_current_execution():
    global CURRENT_PROCESS, CURRENT_TASK, WAS_CANCELLED
    WAS_CANCELLED = True

    if CURRENT_PROCESS and CURRENT_PROCESS.poll() is None:
        try:
            pgid = os.getpgid(CURRENT_PROCESS.pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                CURRENT_PROCESS.kill()
            except Exception:
                pass
        CURRENT_PROCESS = None

    if CURRENT_TASK and not CURRENT_TASK.done():
        CURRENT_TASK.cancel()

    # Clean up any child worker processes
    subprocess.run(["pkill", "-9", "-f", "agy"], capture_output=True)

def run_subprocess_agy(cmd: list, cwd: str, timeout: int = 900):
    global CURRENT_PROCESS
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    CURRENT_PROCESS = proc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        raise
    finally:
        CURRENT_PROCESS = None
    return proc.returncode, stdout, stderr
