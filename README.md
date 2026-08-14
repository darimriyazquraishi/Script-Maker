<div align="center">

<img src="icon.png" width="128" height="128" alt="ScriptMaker Logo" />

# ScriptMaker

**Autonomous Web & YouTube Research + Local AI Script Generator**

*Turn articles, links, and YouTube videos into grounded, production-ready Documentary and High-Retention YouTube Scripts using 100% private, local LLMs.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-brightgreen.svg)](https://doc.qt.io/qtforpython/)
[![LLM Backend](https://img.shields.io/badge/LLM-llama.cpp%20GGUF-orange.svg)](https://github.com/ggerganov/llama.cpp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🚀 Key Features

- **🌐 Deep Multi-Source Research**:
  - Automatically scrapes articles, blog posts, news, and official sources using `trafilatura` and `BeautifulSoup4`.
  - Extracts full transcripts from YouTube videos using `yt-dlp`.
  - Expands research dynamically via free DuckDuckGo search or optional Tavily API.
- **🔒 100% Local & Private AI**:
  - Powered by `llama.cpp` (`llama-server.exe`) running locally on your hardware.
  - Zero API costs, zero data tracking, works offline.
- **⚡ Real-Time Streaming & Activity Logs**:
  - Live Server-Sent Events (SSE) stream words/tokens directly to the screen in real time.
  - Timestamped Activity & Server Console logging CUDA offload, VRAM memory usage, and research progress.
- **🎬 Dual Script Formats**:
  - **Version A — Documentary**: Deep narrative pacing, balanced viewpoints, historical/thematic context, and journalistic neutrality.
  - **Version B — High-Retention YouTube**: Fast conversational pacing, dynamic retention hooks, clear visual cues `[B-ROLL]`, and storytelling payoffs.
- **🧠 Zero-Configuration & Auto-Healing**:
  - Automatically discovers local `llama-server.exe` binaries and GGUF models.
  - Portable design: can be extracted and run on any drive or machine.

---

## 🏆 Recommended GGUF Models

For best quality and high token speed on **8GB–12GB VRAM GPUs** (RTX 3060, 4060, 4070 Super, etc.):

| Model | Recommended Quant | VRAM (with 16k Context) | Inference Speed | Best For |
| :--- | :--- | :--- | :--- | :--- |
| **[Qwen2.5-7B-Instruct](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF)** | `Q4_K_M` or `Q5_K_M` | ~7.5 GB | **~90–110 tok/s** | Deep Research, Structured Briefs, Fast Synthesis |
| **[Meta-Llama-3.1-8B-Instruct](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)** | `Q4_K_M` or `Q5_K_M` | ~8.0 GB | **~85–100 tok/s** | Conversational YouTube Voice, Hooks & Pacing |
| **[Gemma-2-9B-It](https://huggingface.co/bartowski/gemma-2-9b-it-GGUF)** | `Q4_K_M` | ~9.5 GB | **~70–85 tok/s** | Complex Fact Cross-Referencing |

---

## 📥 Installation & Running

### Option 1: Running from Source (Cross-Platform)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ScriptMaker.git
   cd ScriptMaker
   ```

2. **Create a virtual environment & install dependencies**:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **(Optional) Configure environment variables**:
   Copy `.env.example` to `.env` if you want to set custom endpoints:
   ```ini
   LLAMA_SERVER_URL=http://127.0.0.1:8080
   TAVILY_API_KEY=
   ```

4. **Launch the application**:
   ```bash
   python app.py
   # Or on Windows, double click START.bat
   ```

---

### Option 2: Building Standalone Executable (Windows)

To compile a standalone portable Windows binary with PyInstaller:

```bash
python build_exe.py
```

The output will be generated inside `dist/ScriptMaker/`.

---

## 🛠️ Project Structure

```
ScriptMaker/
├── app.py                     # Main PySide6 Desktop GUI & Event Loops
├── pipeline.py                # Research, search enrichment & LLM generation pipeline
├── research.py                # Web article scraper & YouTube caption extractor
├── llm.py                     # LlamaServer client, SSE token streaming & process manager
├── models.py                  # Dataclasses (Source, Evidence, ResearchBrief)
├── requirements.txt           # Python dependency requirements
├── build_exe.py               # Standalone Windows packaging script
├── ScriptMaker.spec           # PyInstaller build specification
├── icon.png / icon.ico        # High-resolution application artwork
├── INSTALL.bat & START.bat    # Quick-launch batch scripts
└── .gitignore                 # GitHub-compatible exclusions
```

---

## 🤝 Contributing

Pull requests and issues are welcome! Feel free to fork the repository, make enhancements, and submit a PR.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
