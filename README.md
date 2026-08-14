<div align="center">

<img src="icon.png" width="128" height="128" alt="ScriptMaker Logo" />

# ScriptMaker

### Web & YouTube Research → Local AI Script Generation

**Turn articles, URLs, and YouTube videos into research-grounded, production-ready YouTube scripts using a local GGUF LLM.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-brightgreen.svg)](https://doc.qt.io/qtforpython/)
[![LLM](https://img.shields.io/badge/LLM-GGUF%20%2B%20llama.cpp-orange.svg)](https://github.com/ggml-org/llama.cpp)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## What is ScriptMaker?

ScriptMaker is a **local-first research and script-generation desktop application** built for YouTube creators, researchers, and anyone who needs to turn multiple sources into a structured video script.

Give it a **topic** and one or more **source URLs**. ScriptMaker collects the available information, researches the subject, builds a compact research brief, and then uses a local GGUF model to generate multiple script versions.

The core idea is simple:

```text
Topic
  +
Source URLs
  +
Optional Web Research
        │
        ▼
   Source Extraction
        │
        ▼
   Research & Evidence
        │
        ▼
  Topic-Specific Brief
        │
        ├───────────────┐
        ▼               ▼
 Documentary       YouTube
  Version A         Version B
```

### Topic vs. Sources

The **topic is the objective**.

The **URLs are research material**.

For example:

```text
Topic:
10 Essential Sci-Fi TV Shows You Need To Watch Before You Die

Sources:
- ScreenRant article
- Collider article
- Rotten Tomatoes guide
- YouTube video
```

ScriptMaker uses those sources as evidence and produces a script specifically about the requested topic.

Multiple sources are combined rather than generating a separate script for each URL.

---

## Key Features

### Web & Multi-Source Research

* Accept multiple URLs at once.
* Extract readable content from articles, blogs, news pages, and other web sources.
* Combine information from multiple sources into a single research set.
* Optionally expand the research beyond the supplied URLs using free web search.
* Optional Tavily integration for enhanced web research.

### YouTube Research

YouTube URLs can be used as research sources.

When captions are available, ScriptMaker extracts the available transcript/captions and uses the text as research material.

```text
YouTube URL
    ↓
Video metadata
    ↓
Captions / transcript
    ↓
Research material
```

This means ScriptMaker does **not need to watch or download the entire video** simply to use its spoken content.

> Caption availability and quality depend on the individual YouTube video. A future/fallback transcription pipeline can be added for videos without usable captions.

### Local AI Generation

Script generation runs through:

**GGUF model + llama.cpp + llama-server**

The model runs locally on your own hardware, so the actual AI writing process does not require OpenAI, Gemini, or another paid LLM API.

This gives you:

* No per-generation LLM API cost
* Local inference
* Full control over the model
* Custom GGUF model support
* Better privacy for the generation stage

### Two Script Versions

#### Version A — Documentary

Designed for:

* Documentary-style narration
* Historical/contextual storytelling
* Balanced presentation
* Slower narrative pacing
* Research-heavy topics

#### Version B — High-Retention YouTube

Designed for:

* Strong opening hooks
* Conversational narration
* Retention-focused pacing
* Storytelling transitions
* Payoffs and curiosity-driven structure
* Visual/B-roll suggestions when enabled

The two versions are generated from the **same research foundation**, allowing you to compare different writing approaches without repeating the research process manually.

### Configurable Script Length

Choose the target script length from the application.

Typical presets include:

```text
Short
Standard
Long
Very Long
```

The selected target is passed to the writing model so the output is structured around a desired video length rather than an arbitrary token limit.

### Real-Time Generation

The application can stream generated output while the model is writing instead of waiting for the entire response to finish.

You can also see progress from:

* Source collection
* Web searches
* Page extraction
* Research generation
* Script generation
* Local llama.cpp server activity

### Portable Windows Application

ScriptMaker can be packaged into a standalone Windows application using PyInstaller.

The packaged build can include:

* Application GUI
* llama.cpp server binary
* Application resources
* Icon/assets
* Launch scripts

The GGUF model itself is **not bundled by default** because model files can be several gigabytes in size.

---

## Privacy & Internet Usage

ScriptMaker is **local-first**, but it is important to distinguish local AI generation from web research.

### Local

The following can run entirely on your machine:

```text
GGUF model
llama.cpp
Script generation
Research summarization
Content planning
```

### Internet-dependent

When using online research, the application may contact:

```text
Websites you provide
Search engines
Optional Tavily API
YouTube
```

Therefore:

> **The LLM inference is local, but web research requires an internet connection and may contact external services.**

You can also use **Supplied Sources Only** mode when you want to restrict research to the URLs you provide.

---

## Research Modes

### Free Web Research

The default local-first research mode.

Uses free web search and direct page extraction without requiring a paid API.

```text
Topic
  ↓
Free search
  ↓
Relevant pages
  ↓
Content extraction
  ↓
Research brief
```

### Supplied Sources Only

Uses only the URLs entered by the user.

Useful when you want strict control over the research material.

```text
Your URLs
   ↓
Extraction
   ↓
Research brief
   ↓
Scripts
```

### Tavily Enhanced

Optional Tavily integration for users who want an external AI-oriented search layer.

A Tavily API key is **not required** for the normal free/local-first workflow.

---

## Recommended Hardware

ScriptMaker is designed to work with local NVIDIA GPU inference through llama.cpp.

A GPU with around **8–12 GB of VRAM** is a practical starting point for smaller quantized models.

For example:

```text
RTX 3060
RTX 4060
RTX 4070 / 4070 Super
```

Your ideal model and quantization depend on:

* VRAM
* Context size
* Model size
* Quantization
* Number of concurrent requests
* Desired generation speed

For single-user desktop generation, a **single llama.cpp server slot** is generally preferable to running multiple large contexts simultaneously.

---

## Recommended GGUF Models

There is no single “best” model for every machine.

For a 8–12 GB VRAM system, sensible starting points are:

| Model                     | Suggested Quantization | Best For                                           |
| :------------------------ | :--------------------- | :------------------------------------------------- |
| **Qwen2.5-7B-Instruct**   | `Q4_K_M` / `Q5_K_M`    | Fast general writing, structured research          |
| **Qwen3-14B**             | `Q4_K_M`               | Higher-quality reasoning and longer-form writing   |
| **Llama 3.1 8B Instruct** | `Q4_K_M` / `Q5_K_M`    | Conversational writing and YouTube-style narration |
| **Gemma 2 9B IT**         | `Q4_K_M`               | General reasoning and synthesis                    |

Model performance varies significantly by hardware and llama.cpp configuration, so benchmark your chosen model locally rather than relying on generic token-per-second estimates.

---

## Installation

### Option 1 — One-Click Windows Setup

For Windows users, the easiest method is:

```text
INSTALL.bat
```

The installer will:

1. Check for Python.
2. Create the virtual environment.
3. Install Python dependencies.
4. Create the local configuration file.
5. Run an installation check.

After installation:

```text
START.bat
```

launches ScriptMaker.

---

### Option 2 — Run From Source

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/ScriptMaker.git
cd ScriptMaker
```

Create a virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example` if you want to customize settings:

```env
LLAMA_SERVER_URL=http://127.0.0.1:8080
TAVILY_API_KEY=
RESEARCH_MODE=free
```

Launch:

```bash
python app.py
```

---

## Local llama.cpp Setup

ScriptMaker communicates with a local `llama-server` instance.

Example:

```bash
llama-server.exe ^
  -m "C:\AI\Models\Qwen3-14B-Q4_K_M.gguf" ^
  -ngl 99 ^
  -c 16384 ^
  -np 1 ^
  -fa on ^
  --host 127.0.0.1 ^
  --port 8080
```

The application expects the server at:

```text
http://127.0.0.1:8080
```

### Why these settings?

For a single-user desktop application, using one server slot avoids unnecessarily allocating multiple large context windows.

A smaller context also reduces memory pressure and prompt-processing overhead.

Adjust the values according to your GPU and model.

---

## Building the Standalone Windows Version

ScriptMaker can be packaged with PyInstaller.

Run:

```bash
python build_exe.py
```

The output will be created under:

```text
dist/ScriptMaker/
```

The build can contain the application and llama.cpp runtime, while the GGUF model can remain in a separate location.

---

## How ScriptMaker Works

### 1. Source Collection

ScriptMaker reads the supplied URLs.

```text
URL
 ↓
Page detection
 ↓
Article / YouTube extraction
```

### 2. Web Research

In free research mode, ScriptMaker can expand the initial information using additional searches.

```text
Topic
 ↓
Search queries
 ↓
Relevant pages
 ↓
Page extraction
```

### 3. Evidence & Research

The collected material is reduced into a structured, topic-specific research brief.

This stage helps separate:

* Key facts
* Timeline information
* Important people
* Relevant context
* Conflicting claims
* Unknown/uncertain information

### 4. Content Planning

The research brief is converted into a writing plan based on the requested topic.

### 5. Script Generation

The local GGUF model receives the compact research material and generates:

```text
Version A → Documentary
Version B → High-Retention YouTube
```

This separation keeps the script-writing prompt smaller and avoids repeatedly sending the entire raw research dataset to the model.

---

## Project Structure

```text
ScriptMaker/
│
├── app.py
│   └── Main PySide6 application and UI
│
├── pipeline.py
│   └── Research → planning → script generation pipeline
│
├── research.py
│   └── Web extraction, search, and YouTube processing
│
├── llm.py
│   └── llama-server client, streaming, and local model management
│
├── models.py
│   └── Research/source/evidence data structures
│
├── requirements.txt
│   └── Python dependencies
│
├── build_exe.py
│   └── Windows standalone build script
│
├── ScriptMaker.spec
│   └── PyInstaller configuration
│
├── icon.png
├── icon.ico
│   └── Application artwork
│
├── INSTALL.bat
│   └── One-click environment setup
│
├── START.bat
│   └── Application launcher
│
└── .gitignore
```

---

## Important Notes

### ScriptMaker does not replace source verification

The application is designed to be **research-grounded**, not infallible.

Different sources can contain:

* Errors
* Outdated information
* Opinions
* Conflicting claims
* Automatically generated text

Always verify important claims before publishing.

### YouTube transcripts are not automatically authoritative

A transcript represents what was said in the video. It does not guarantee that the information itself is correct.

### Search results can change

Free web search depends on external services and may experience:

* Rate limits
* Temporary failures
* Search-result changes
* Blocked pages
* Extraction failures

ScriptMaker therefore keeps the supplied URLs as a primary research input.

---

## Contributing

Issues, feature requests, pull requests, and improvements are welcome.

Some areas that can be expanded include:

* Better source ranking
* Claim-level citation tracking
* Automatic contradiction detection
* More YouTube transcription fallbacks
* Additional script formats
* Custom prompt templates
* Additional local models
* Improved caching
* Cross-platform packaging

---

## License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**ScriptMaker — Research locally. Write intelligently.**

</div>
