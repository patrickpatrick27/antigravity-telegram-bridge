import re
import html
import logging
from telegram import Update

logger = logging.getLogger("antigravity-bot.formatter")

def md_to_telegram_html(md: str) -> str:
    if not md:
        return ""

    code_blocks = []
    def save_code_block(match):
        lang = match.group(1).strip()
        code = match.group(2)
        idx = len(code_blocks)
        esc_code = html.escape(code.strip(), quote=False)
        if lang:
            tag = f'<pre><code class="language-{lang}">{esc_code}</code></pre>'
        else:
            tag = f'<pre><code>{esc_code}</code></pre>'
        code_blocks.append(tag)
        return f"@@@CODEBLOCK_{idx}@@@"

    md = re.sub(r'```([a-zA-Z0-9_-]*)\n?(.*?)```', save_code_block, md, flags=re.DOTALL)

    inline_codes = []
    def save_inline_code(match):
        code = match.group(1)
        idx = len(inline_codes)
        esc_code = html.escape(code, quote=False)
        inline_codes.append(f'<code>{esc_code}</code>')
        return f"@@@INLINECODE_{idx}@@@"

    md = re.sub(r'`([^`\n]+)`', save_inline_code, md)

    links = []
    def save_link(match):
        text = match.group(1)
        url = match.group(2).strip()
        idx = len(links)
        esc_text = html.escape(text, quote=False)
        esc_url = url.replace('"', '%22')
        links.append(f'<a href="{esc_url}">{esc_text}</a>')
        return f"@@@LINK_{idx}@@@"

    md = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', save_link, md)

    # Escape remaining HTML sensitive characters (do NOT escape quotes/apostrophes in text)
    md = html.escape(md, quote=False)

    # Headers: ### Header -> <b>Header</b>
    md = re.sub(r'^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$', r'<b>\1</b>', md, flags=re.MULTILINE)

    # Bold: **text** or __text__ -> <b>text</b>
    md = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', md)
    md = re.sub(r'__(.+?)__', r'<b>\1</b>', md)

    # Italic: *text* or _text_ -> <i>text</i>
    md = re.sub(r'(?<!\w)\*([^\*\n]+)\*(?!\w)', r'<i>\1</i>', md)
    md = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'<i>\1</i>', md)

    # Strikethrough: ~~text~~ -> <s>text</s>
    md = re.sub(r'~~(.+?)~~', r'<s>\1</s>', md)

    # Lists: * item or - item -> • item
    md = re.sub(r'^[ \t]*[\*\-][ \t]+', r'• ', md, flags=re.MULTILINE)

    # Blockquotes: > text -> <blockquote>text</blockquote>
    md = re.sub(r'^[ \t]*&gt;[ \t]*(.+?)$', r'<blockquote>\1</blockquote>', md, flags=re.MULTILINE)

    # Clean horizontal rules --- -> ──────────
    md = re.sub(r'^[ \t]*[\-\*_]{3,}[ \t]*$', r'──────────', md, flags=re.MULTILINE)

    # Restore placeholders
    for idx, block in enumerate(code_blocks):
        md = md.replace(f"@@@CODEBLOCK_{idx}@@@", block)
    for idx, incode in enumerate(inline_codes):
        md = md.replace(f"@@@INLINECODE_{idx}@@@", incode)
    for idx, link_tag in enumerate(links):
        md = md.replace(f"@@@LINK_{idx}@@@", link_tag)

    return md.strip()

def chunk_telegram_text(text: str, max_size: int = 3800) -> list[str]:
    if not text or len(text) <= max_size:
        return [text] if text else []
    
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p) + 2
        if current_len + p_len > max_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p]
            current_len = len(p)
        else:
            current_chunk.append(p)
            current_len += p_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    final_chunks = []
    for c in chunks:
        if len(c) <= max_size:
            final_chunks.append(c)
        else:
            lines = c.split("\n")
            sub_chunk = []
            sub_len = 0
            for l in lines:
                if sub_len + len(l) + 1 > max_size and sub_chunk:
                    final_chunks.append("\n".join(sub_chunk))
                    sub_chunk = [l]
                    sub_len = len(l)
                else:
                    sub_chunk.append(l)
                    sub_len += len(l) + 1
            if sub_chunk:
                final_chunks.append("\n".join(sub_chunk))
    return final_chunks

async def send_chunked_message(update: Update, raw_markdown: str, status_msg=None):
    if not raw_markdown or not raw_markdown.strip():
        raw_markdown = "(Empty response from Antigravity)"
    
    formatted_html = md_to_telegram_html(raw_markdown)
    chunks = chunk_telegram_text(formatted_html, max_size=3800)

    start_idx = 0
    if status_msg and chunks:
        first_chunk = chunks[0]
        try:
            await status_msg.edit_text(first_chunk, parse_mode="HTML", disable_web_page_preview=True)
            start_idx = 1
        except Exception:
            try:
                clean_plain = re.sub(r'<[^>]+>', '', first_chunk)
                await status_msg.edit_text(clean_plain, parse_mode=None, disable_web_page_preview=True)
                start_idx = 1
            except Exception:
                try:
                    await status_msg.delete()
                except Exception:
                    pass

    for chunk in chunks[start_idx:]:
        if not chunk.strip():
            continue
        try:
            await update.message.reply_text(chunk, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"HTML send failed ({e}), stripping tags and sending plain text")
            clean_plain = re.sub(r'<[^>]+>', '', chunk)
            try:
                await update.message.reply_text(clean_plain, parse_mode=None, disable_web_page_preview=True)
            except Exception as ex:
                logger.error(f"Failed to send chunk: {ex}")
