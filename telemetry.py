import os
import json
import logging
from datetime import datetime, timezone
from config import BASE_DIR

logger = logging.getLogger("antigravity-bridge.telemetry")
TELEMETRY_FILE = os.path.join(BASE_DIR, "telemetry.jsonl")

def record_turn_telemetry(model_id: str, usage: dict, duration: float, conversation_id: str = None):
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model_id,
            "duration_seconds": round(duration, 2),
            "input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens") or 0,
            "output_tokens": usage.get("completion_tokens") or usage.get("output_tokens") or 0,
            "thinking_tokens": usage.get("thinking_tokens") or 0,
            "total_tokens": usage.get("total_tokens") or 0,
            "conversation_id": conversation_id,
        }
        with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"Error recording telemetry: {e}")

def get_last_turn_telemetry() -> dict | None:
    if not os.path.exists(TELEMETRY_FILE):
        return None
    try:
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1].strip())
    except Exception:
        pass
    return None

def build_stats_message() -> str:
    if not os.path.exists(TELEMETRY_FILE):
        return "📊 <b>Session Telemetry:</b> No turn data logged yet."

    turns_by_model = {}
    total_turns = 0
    total_input = 0
    total_output = 0
    total_thinking = 0
    total_dur = 0.0

    try:
        with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    m = data.get("model", "unknown")
                    inp = data.get("input_tokens", 0)
                    out = data.get("output_tokens", 0)
                    thk = data.get("thinking_tokens", 0)
                    dur = data.get("duration_seconds", 0.0)

                    if m not in turns_by_model:
                        turns_by_model[m] = {"turns": 0, "inp": 0, "out": 0, "thk": 0, "dur": 0.0}

                    turns_by_model[m]["turns"] += 1
                    turns_by_model[m]["inp"] += inp
                    turns_by_model[m]["out"] += out
                    turns_by_model[m]["thk"] += thk
                    turns_by_model[m]["dur"] += dur

                    total_turns += 1
                    total_input += inp
                    total_output += out
                    total_thinking += thk
                    total_dur += dur
                except Exception:
                    continue
    except Exception as e:
        return f"⚠️ Error reading telemetry log: {e}"

    if total_turns == 0:
        return "📊 <b>Session Telemetry:</b> No turns recorded yet."

    avg_latency = round(total_dur / total_turns, 1)

    lines = [
        "📊 <b>Agent Telemetry & Token Burn:</b>\n",
        f"• <b>Total Turns Recorded:</b> <code>{total_turns}</code>",
        f"• <b>Avg Turn Latency:</b> <code>{avg_latency}s</code>",
        f"• <b>Total Input Tokens:</b> <code>{total_input:,}</code>",
        f"• <b>Total Output Tokens:</b> <code>{total_output:,}</code>",
    ]
    if total_thinking > 0:
        lines.append(f"• <b>Thinking Tokens:</b> <code>{total_thinking:,}</code>")

    lines.append("\n<b>Breakdown by Model:</b>")
    for m, stat in turns_by_model.items():
        m_avg = round(stat["dur"] / stat["turns"], 1) if stat["turns"] > 0 else 0
        lines.append(
            f"• <code>{m}</code>: <b>{stat['turns']} turns</b> | "
            f"Avg {m_avg}s | "
            f"In: {stat['inp']:,} | Out: {stat['out']:,}"
        )

    last = get_last_turn_telemetry()
    if last:
        lines.append(
            f"\n⚡ <b>Last Turn:</b> <code>{last.get('model')}</code> in "
            f"<b>{last.get('duration_seconds')}s</b> (Total: {last.get('total_tokens'):,} tokens)"
        )

    return "\n".join(lines)
