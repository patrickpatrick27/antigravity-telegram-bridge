import os

def load_env(env_path):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(BASE_DIR, ".env"))

# Telegram Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Antigravity CLI & Workspace Settings
DEFAULT_WORKSPACE = os.getenv("DEFAULT_WORKSPACE", os.path.expanduser("~"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.7-flash-medium")
AGY_BIN = os.path.expanduser(os.getenv("AGY_BIN", "~/.local/bin/agy"))
STATE_FILE = os.path.join(BASE_DIR, "state.json")

# Google OAuth Credentials (Optional: for /pin quota tracking)
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "")

# Supported Model Registry
AVAILABLE_MODELS = {
    # Claude Models
    "sonnet": ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)"),
    "claude": ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)"),
    "claude-sonnet": ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)"),
    "claude-sonnet-4-6": ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)"),
    "opus": ("claude-opus-4-6-thinking", "Claude Opus 4.6 (Thinking)"),
    "claude-opus": ("claude-opus-4-6-thinking", "Claude Opus 4.6 (Thinking)"),
    "claude-opus-4-6-thinking": ("claude-opus-4-6-thinking", "Claude Opus 4.6 (Thinking)"),
    # Gemini 3.7 Flash (Medium Effort - Default)
    "gemini": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "flash": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "gemini-medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "gemini_medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "geminimedium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "flash-medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "flash_medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "flashmedium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    "gemini-3.7-flash-medium": ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)"),
    # Gemini 3.7 Flash (High Effort)
    "high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "gemini-high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "gemini_high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "geminihigh": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "flash-high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "flash_high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "flashhigh": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    "gemini-3.7-flash-high": ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
    # Gemini 3.7 Flash (Low Effort)
    "low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "gemini-low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "gemini_low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "geminilow": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "flash-low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "flash_low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "flashlow": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    "gemini-3.7-flash-low": ("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)"),
    # Gemini Pro
    "pro": ("gemini-3.1-pro-high", "Gemini 3.1 Pro (High)"),
    "gemini-3.1-pro-high": ("gemini-3.1-pro-high", "Gemini 3.1 Pro (High)"),
    # Open Models
    "gpt": ("gpt-oss-120b-medium", "GPT-OSS 120B (Medium)"),
    "gpt-oss": ("gpt-oss-120b-medium", "GPT-OSS 120B (Medium)"),
    "gpt-oss-120b-medium": ("gpt-oss-120b-medium", "GPT-OSS 120B (Medium)"),
}

MODEL_DISPLAY_NAMES = {
    "claude-sonnet-4-6": "Claude Sonnet 4.6 (Thinking)",
    "claude-opus-4-6-thinking": "Claude Opus 4.6 (Thinking)",
    "gemini-3.7-flash-high": "Gemini 3.7 Flash (High)",
    "gemini-3.7-flash-medium": "Gemini 3.7 Flash (Medium)",
    "gemini-3.7-flash-low": "Gemini 3.7 Flash (Low)",
    "gemini-3.1-pro-high": "Gemini 3.1 Pro (High)",
    "gpt-oss-120b-medium": "GPT-OSS 120B (Medium)",
}

def is_authorized(user_id: int) -> bool:
    if ALLOWED_USER_ID == 0:
        return False
    return user_id == ALLOWED_USER_ID
