import json
import os
import shutil
import subprocess
import sys
import time
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

    # 1. Priority: Bundled internal llama-server from PyInstaller _MEIPASS
    bundled = get_bundle_dir() / "llama" / "llama-server.exe"
    if bundled.exists() and bundled.is_file():
        return str(bundled.resolve())

    # 2. Priority: Adjacent llama folder next to exe or in current workspace
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


import threading


class LlamaServerProcess:
    def __init__(self, exe_path: str, model_path: str, port: int = 8080, ngl: int = 99, context: int = 32768, log_callback=None):
        self.exe_path = exe_path
        self.model_path = model_path
        self.port = port
        self.ngl = ngl
        self.context = context
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
            "--host", "127.0.0.1",
            "--port", str(self.port)
        ]

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

    def health(self):
        try:
            r = requests.get(self.base_url + "/health", timeout=4)
            return r.ok
        except Exception:
            return False

    def wait_until_ready(self, timeout_sec=90, progress_cb=None):
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.health():
                return True
            if progress_cb:
                elapsed = int(time.time() - start)
                progress_cb(f"Waiting for local LLM server ({elapsed}s)...")
            time.sleep(2)
        return False

    def chat_stream(self, system: str, user: str, temperature=0.4, max_tokens=5000, on_token=None, on_progress=None):
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

        for line in r.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if line_str.startswith("data: "):
                data_str = line_str[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            collected.append(content)
                            token_count += 1
                            if on_token:
                                on_token(content)
                            if on_progress and (time.time() - last_progress_time > 1.0 or token_count % 25 == 0):
                                on_progress(f"Generated {token_count} tokens...")
                                last_progress_time = time.time()
                except Exception:
                    pass

        return "".join(collected)

    def chat(self, system: str, user: str, temperature=0.4, max_tokens=5000, on_token=None, on_progress=None):
        try:
            return self.chat_stream(system, user, temperature, max_tokens, on_token=on_token, on_progress=on_progress)
        except Exception:
            # Fallback to non-streaming if stream fails
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
You are a research-grounded content writer.

Rules:
- Use only facts present in the supplied research material.
- Never invent names, dates, quotes, events, statistics, or sources.
- When sources conflict, explicitly describe the uncertainty.
- Prefer official/primary material when it exists.
- Do not present an unverified claim as confirmed.
- Distinguish between source reporting and confirmed facts.
- Write naturally for a human audience.
- You may improve structure and phrasing, but must not add unsupported facts.
""".strip()


def _material_from_sources(sources, web_results):
    material = []

    for source in sources:
        if source.get("content"):
            material.append(
                f"SOURCE: {source.get('title')}\n"
                f"TYPE: {source.get('source_type')}\n"
                f"URL: {source.get('url')}\n"
                f"CONTENT:\n{source.get('content', '')[:9000]}"
            )

    for item in web_results:
        content = (
            item.get("extracted_content")
            or item.get("raw_content")
            or item.get("content")
            or ""
        )
        if content:
            material.append(
                f"SEARCH RESULT: {item.get('title')}\n"
                f"URL: {item.get('url')}\n"
                f"CONTENT:\n{content[:7000]}"
            )

    return "\n\n---\n\n".join(material)


def research_brief_prompt(topic, sources, web_results):
    material = _material_from_sources(sources, web_results)

    return f"""
Topic: {topic}

Create a research brief in JSON with exactly these keys:
summary
key_facts
timeline
people
conflicts
unknowns

Rules:
- All list values must be arrays of strings.
- Keep every claim grounded in the supplied material.
- Put unresolved contradictions in conflicts.
- Put missing or weakly supported information in unknowns.
- Do not invent details merely to make the brief complete.

MATERIAL:
{material}
""".strip()


def script_prompt(brief, style):
    if style == "documentary":
        style_instructions = """
Style:
- documentary and factual
- calm, clear narration
- chronological when helpful
- informative rather than exaggerated
- explain context before conclusions
"""
    else:
        style_instructions = """
Style:
- high-retention YouTube
- strong opening hook
- conversational narration
- short paragraphs
- curiosity-driven transitions
- build toward the most interesting confirmed details
- avoid unsupported clickbait
"""

    return f"""
Create a complete YouTube script from the research brief below.

{style_instructions}

Structure:
1. Hook
2. Introduction
3. Main story
4. Important context
5. Latest/most relevant confirmed information
6. Conclusion

Do not invent anything that is not supported by the brief.
When a fact is uncertain, clearly phrase it as uncertain.

At the end, include a short "Sources to verify" section listing the URLs
represented by the research material.

RESEARCH BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}
""".strip()
