# ScriptMaker — Clean Source Code

ScriptMaker is a desktop application for automated web and YouTube research, evidence synthesis, and local AI script generation (Documentary and High-Retention YouTube scripts).

## Project Architecture

- **`app.py`**: PySide6 GUI interface. Features:
  - Local GGUF file browser (`QFileDialog`).
  - Auto-detected `llama-server.exe` integration and auto-healing paths.
  - Server lifecycle management (Start/Restart/Stop, GPU layers `ngl`, Context `-c`).
  - Real-time token streaming direct to output tabs via Server-Sent Events (SSE).
  - Activity & Server Logs console with timestamped stdout streaming.
  - Project save/export functionality (Markdown & JSON).
- **`pipeline.py`**: Core pipeline orchestrating URL collection, DuckDuckGo/Tavily search enrichment, fact extraction, and multi-prompt LLM generation.
- **`research.py`**: Web scraper (Trafilatura + BeautifulSoup), YouTube caption parser (`yt-dlp`), and search engine wrappers.
- **`llm.py`**: `LlamaServer` client with streaming SSE (`chat_stream`), background process launcher (`LlamaServerProcess`), and automatic model/binary discovery.
- **`models.py`**: Data structures for `Source`, `Evidence`, and `ResearchBrief`.
- **`build_exe.py`**: Automated script to build the portable Windows folder using PyInstaller.
- **`ScriptMaker.spec`**: PyInstaller build specification.

---

## Setup & Running from Source

### 1. Install Dependencies
Make sure you have Python 3.10+ installed.

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Windows CMD:
.venv\Scripts\activate.bat

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```ini
LLAMA_SERVER_URL=http://127.0.0.1:8080
TAVILY_API_KEY=
```

### 3. Run Application
```bash
python app.py
```

---

## Building Portable Executable

To compile into a portable folder:

```bash
python build_exe.py
```

The output will be created in `dist/ScriptMaker/` containing `ScriptMaker.exe`, dependencies, and llama binaries.

---

## Recommended GGUF Models

For best performance on 8GB–12GB VRAM GPUs (like RTX 3060, 4060, 4070 Super):
- **`Qwen2.5-7B-Instruct-Q4_K_M.gguf`** (Fastest, best for research and structured briefs)
- **`Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`** (Best natural conversational style for YouTube)
- **`gemma-2-9b-it-Q4_K_M.gguf`** (High reasoning and factual synthesis)

## Performance/quality update

The optimized build uses:
- one llama.cpp server slot (`-np 1`) because ScriptMaker is single-user/single-generation;
- Flash Attention (`-fa on`);
- 16,384 default context instead of 32,768;
- a bounded research input instead of dumping many full pages into every prompt;
- a compact `content_plan` research brief for script writing;
- raw source/evidence data retained for the UI/export but excluded from script prompts;
- explicit script length targets (Short / Standard / Long / Very Long);
- stronger prompts for list/count topics so a "10"-item video is actually planned as 10 items when supported.

### Rebuild the Windows EXE

The ZIP includes the updated Python source and build scripts, but the previously compiled `ScriptMaker.exe` cannot be magically patched in-place. Rebuild it on the machine that has your `llama/` folder:

```bat
python build_exe.py
```

The output will be in `dist\\ScriptMaker\\`.

After rebuilding, keep your `llama\\llama-server.exe` and model in the same portable structure used by your current build.
