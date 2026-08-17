import json
import os
import shutil
import subprocess
import sys
import time
import threading
import re
from pathlib import Path

import requests


def get_app_dir():
    """Return base directory of the application next to executable or source."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def get_bundle_dir():
    """Return internal PyInstaller extraction folder if frozen, or source directory."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def find_llama_server_exe(custom_path=None):
    """Find llama-server.exe binary, prioritizing internal bundled server."""
    if custom_path and os.path.isfile(custom_path):
        return os.path.abspath(custom_path)

    bundled = get_bundle_dir() / "llama" / "llama-server.exe"
    if bundled.exists() and bundled.is_file():
        return str(bundled.resolve())

    app_dir = get_app_dir()
    candidates = [
        app_dir / "llama" / "llama-server.exe",
        Path(os.getcwd()) / "llama" / "llama-server.exe",
        Path("C:/AI/llama.cpp/llama-server.exe"),
        Path(os.path.expanduser("~/llama.cpp/llama-server.exe")),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

    which = shutil.which("llama-server.exe")
    if which:
        return os.path.abspath(which)
    return ""


def find_default_gguf_model(custom_path=None):
    """Find default GGUF model file in models folder."""
    if custom_path and os.path.isfile(custom_path):
        return os.path.abspath(custom_path)

    app_dir = get_app_dir()
    dirs_to_check = [app_dir / "models", Path(os.getcwd()) / "models"]
    for d in dirs_to_check:
        if d.exists() and d.is_dir():
            gguf_files = list(d.glob("*.gguf"))
            if gguf_files:
                return str(gguf_files[0].resolve())
    return ""


class LlamaServerProcess:
    """
    Launch a single-user llama.cpp server tuned for ScriptMaker.

    The application generates one request at a time, so multiple 32k server
    slots waste VRAM. We intentionally use a single slot plus Flash Attention.
    """

    def __init__(
        self,
        exe_path: str,
        model_path: str,
        port: int = 8080,
        ngl: int = 99,
        context: int = 16384,
        parallel: int = 1,
        flash_attention: bool = True,
        log_callback=None,
    ):
        self.exe_path = exe_path
        self.model_path = model_path
        self.port = port
        self.ngl = ngl
        self.context = context
        self.parallel = parallel
        self.flash_attention = flash_attention
        self.log_callback = log_callback
        self.process = None
        self._reader_thread = None

    def _reader(self):
        if not self.process or not self.process.stdout:
            return
        for line in iter(self.process.stdout.readline, ''):
            if not line:
                break
            stripped = line.rstrip()
            if self.log_callback:
                self.log_callback(stripped)

    def start(self):
        if not self.exe_path or not os.path.isfile(self.exe_path):
            raise FileNotFoundError(f"llama-server executable not found at: {self.exe_path}")
        if not self.model_path or not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"GGUF model file not found at: {self.model_path}")

        cmd = [
            self.exe_path,
            "-m", self.model_path,
            "-ngl", str(self.ngl),
            "-c", str(self.context),
            "-np", str(self.parallel),
            "-fa", "on" if self.flash_attention else "off",
            "--host", "127.0.0.1",
            "--port", str(self.port),
        ]

        if self.log_callback:
            self.log_callback(
                f"[llama] Command: {' '.join(cmd)}"
            )

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            text=True,
            bufsize=1,
        )

        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()
        return self.process

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


class LlamaServer:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def health(self, timeout=1.0):
        try:
            r = requests.get(self.base_url + "/health", timeout=timeout)
            return r.ok
        except Exception:
            return False

    def wait_until_ready(self, timeout_sec=90, progress_cb=None):
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.health(timeout=1.5):
                return True
            if progress_cb:
                elapsed = int(time.time() - start)
                progress_cb(f"Waiting for local LLM server ({elapsed}s)...")
            time.sleep(2)
        return False

    def chat_stream(
        self,
        system: str,
        user: str,
        temperature=0.4,
        max_tokens=6000,
        on_token=None,
        on_progress=None,
    ):
        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        r = requests.post(
            self.base_url + "/v1/chat/completions",
            json=payload,
            timeout=900,
            stream=True,
        )
        r.raise_for_status()

        collected = []
        token_count = 0
        last_progress_time = time.time()
        finish_reason = None

        for line in r.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if not line_str.startswith("data: "):
                continue

            data_str = line_str[6:].strip()
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if choices[0].get("finish_reason"):
                    finish_reason = choices[0].get("finish_reason")
                if content:
                    collected.append(content)
                    token_count += 1
                    if on_token:
                        on_token(content)
                    if on_progress and (time.time() - last_progress_time > 1.0 or token_count % 30 == 0):
                        on_progress(f"Generated {token_count} tokens...")
                        last_progress_time = time.time()
            except Exception:
                pass

        full_text = "".join(collected)

        # If generation was forcefully stopped by token limit before finishing,
        # perform an auto-continuation to guarantee a complete script ending.
        if finish_reason == "length" and token_count >= max_tokens - 10:
            if on_progress:
                on_progress("Auto-completing remaining script ending...")
            continuation = self._continue_completion(system, user, full_text, on_token=on_token)
            if continuation:
                full_text += "\n" + continuation

        return full_text

    def _continue_completion(self, system: str, user: str, generated_text: str, on_token=None):
        """Seamlessly continue generation if token limit was reached prematurely."""
        try:
            last_context = generated_text[-1200:]
            continuation_prompt = (
                f"You were writing the script below, but reached the token limit before concluding:\n\n"
                f"...[Previous text]...\n{last_context}\n\n"
                f"CONTINUATION TASK: Seamlessly continue and finish the remaining points and write the final Conclusion and Outro call-to-action. "
                f"Do not repeat previous text. Finish the script completely."
            )
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": generated_text},
                    {"role": "user", "content": "Please write the conclusion and wrap up the script now."},
                ],
                "temperature": 0.4,
                "max_tokens": 2000,
                "stream": True,
            }
            r = requests.post(self.base_url + "/v1/chat/completions", json=payload, timeout=300, stream=True)
            if not r.ok:
                return ""
            extra_tokens = []
            for line in r.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace")
                if line_str.startswith("data: "):
                    d_str = line_str[6:].strip()
                    if d_str == "[DONE]":
                        break
                    try:
                        c_json = json.loads(d_str)
                        c_text = c_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if c_text:
                            extra_tokens.append(c_text)
                            if on_token:
                                on_token(c_text)
                    except Exception:
                        pass
            return "".join(extra_tokens)
        except Exception:
            return ""

    def chat(self, system: str, user: str, temperature=0.4, max_tokens=6000, on_token=None, on_progress=None):
        try:
            return self.chat_stream(
                system,
                user,
                temperature,
                max_tokens,
                on_token=on_token,
                on_progress=on_progress,
            )
        except Exception:
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            r = requests.post(
                self.base_url + "/v1/chat/completions",
                json=payload,
                timeout=900,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]


SYSTEM_PROMPT = """
You are ScriptMaker, a research-grounded long-form YouTube writer.

NON-NEGOTIABLE FACT RULES:
- Use only facts supported by the supplied research brief.
- Never invent names, dates, quotes, events, statistics, release information, or sources.
- Treat conflicts as conflicts; do not silently choose a side.
- Distinguish confirmed facts from reported or uncertain information.
- Do not pad the script with generic trivia that is absent from the brief.

WRITING RULES:
- Write for spoken narration, not an essay.
- Use varied sentence length and natural transitions.
- Avoid repetitive "This show..." / "Another reason..." patterns.
- Give each item enough development to feel worthwhile.
- Prioritize specificity, context, and storytelling.
""".strip()


def _trim(text, limit):
    text = text or ""
    return text[:limit].strip()


def _material_from_sources(sources, web_results):
    """Build a bounded research input so the model never receives huge raw dumps."""
    material = []
    max_sources = 6

    for source in sources[:max_sources]:
        content = _trim(source.get("content"), 4000)
        if content:
            material.append(
                f"SOURCE: {source.get('title')}\n"
                f"TYPE: {source.get('source_type')}\n"
                f"URL: {source.get('url')}\n"
                f"CONTENT:\n{content}"
            )

    for item in web_results[:max_sources]:
        content = _trim(
            item.get("extracted_content")
            or item.get("raw_content")
            or item.get("content"),
            2500,
        )
        if content:
            material.append(
                f"SEARCH RESULT: {item.get('title')}\n"
                f"URL: {item.get('url')}\n"
                f"CONTENT:\n{content}"
            )

    return "\n\n---\n\n".join(material)


def research_brief_prompt(topic, sources, web_results):
    material = _material_from_sources(sources, web_results)

    return f"""
Topic: {topic}

Create a compact, high-value research brief for a future YouTube writer.
Return JSON with exactly these keys:
summary
key_facts
timeline
people
conflicts
unknowns
content_plan

`content_plan` must be an array of objects. Each object should contain:
- title
- angle
- key_facts (3-6 concise, evidence-grounded bullets)
- source_urls (the URLs that support this item)

For list/count topics, create exactly the requested number of items when the
sources support that count. Example: if the topic says "10 shows", create 10
content_plan objects. Do not invent missing items; use unknowns when evidence
is insufficient.

Rules:
- All list values must be arrays.
- Keep claims grounded in the supplied material.
- Put contradictions in conflicts.
- Put missing or weakly supported information in unknowns.
- Do not copy whole articles.
- Prefer concise facts over long prose.

MATERIAL:
{material}
""".strip()


def script_prompt(brief, style, target_words=1000, target_minutes=5):
    if style == "documentary":
        style_instructions = """
Style:
- Documentary and investigative tone
- Calm, authoritative, engaging spoken narration
- Deep context, historical background, and nuanced analysis
- Smooth, natural transitions between chapters
"""
    else:
        style_instructions = """
Style:
- High-retention YouTube storytelling
- Immediate punchy opening hook
- Conversational, rhythmic spoken narration
- Curiosity-driven transitions that pull the viewer forward
- High-energy payoffs and actionable takeaways
- Formatted visual directions as [B-ROLL: ...] where helpful
"""

    content_plan = brief.get("content_plan", [])
    compact_brief = {
        "topic": brief.get("topic", ""),
        "summary": brief.get("summary", ""),
        "key_facts": brief.get("key_facts", []),
        "timeline": brief.get("timeline", []),
        "people": brief.get("people", []),
        "conflicts": brief.get("conflicts", []),
        "unknowns": brief.get("unknowns", []),
        "content_plan": content_plan,
    }

    return f"""Write a COMPLETE, production-ready script based ONLY on the research brief below.

TARGET DURATION & LENGTH:
- Target Video Duration: approximately {target_minutes} minutes
- Approximate Word Count: ~{target_words} words (based on dynamic spoken YouTube video pacing of ~200 words/minute)

{style_instructions}

SCRIPT STRUCTURE REQUIREMENTS:
1. [Hook] (10-15% of length): Gripping opening statement that hooks the viewer instantly.
2. [Introduction] (10-15% of length): Frame the subject, stakes, and why this matters.
3. [Main Body] (60-70% of length): Cover the main points and content_plan thoroughly with substance, context, and storytelling.
4. [Conclusion & Outro] (10% of length): Memorable wrap-up, final insight, and YouTube call-to-action.

CRITICAL COMPLETION RULES:
- You MUST write the ENTIRE script from Hook to Conclusion/Outro.
- Budget your words across the sections so the script finishes with a complete Conclusion within the target duration.
- NEVER stop abruptly or end mid-sentence.
- Do NOT include source bibliographies inside narration text.
- Do NOT repeat the video title in every sentence.

RESEARCH BRIEF:
{json.dumps(compact_brief, ensure_ascii=False, indent=2)}
""".strip()
