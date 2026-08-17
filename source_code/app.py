import json
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QObject, QThread, Signal, QTimer, Qt
from PySide6.QtGui import QTextCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFormLayout,
    QGroupBox,
    QSpinBox,
)

from pipeline import generate
from research import normalize_urls
from llm import (
    LlamaServer,
    LlamaServerProcess,
    find_llama_server_exe,
    find_default_gguf_model,
    get_app_dir,
    get_bundle_dir,
)

load_dotenv()

CONFIG_FILE_NAME = "config.json"


def get_icon_path():
    for base in [get_bundle_dir(), get_app_dir(), Path(".")]:
        for name in ["icon.png", "icon.ico"]:
            p = base / name
            if p.exists():
                return str(p.resolve())
    return ""


def load_config():
    config_path = get_app_dir() / CONFIG_FILE_NAME
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data):
    try:
        config_path = get_app_dir() / CONFIG_FILE_NAME
        config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class ServerLogBridge(QObject):
    log_message = Signal(str)


class ServerWaitThread(QThread):
    progress = Signal(str)
    ready = Signal(bool)

    def __init__(self, llama_url: str, timeout_sec: int = 90):
        super().__init__()
        self.llama_url = llama_url
        self.timeout_sec = timeout_sec

    def run(self):
        llama = LlamaServer(self.llama_url)
        start = time.time()
        while time.time() - start < self.timeout_sec:
            if llama.health(timeout=1.5):
                self.ready.emit(True)
                return
            elapsed = int(time.time() - start)
            self.progress.emit(f"Waiting for local server readiness ({elapsed}s)...")
            time.sleep(1.5)
        self.ready.emit(False)


class Worker(QThread):
    progress = Signal(str)
    stream_token = Signal(str, str)  # section, token
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, urls, topic, mode, tavily_key, llama_url, llama_exe, gguf_model, ngl, context, target_words, target_minutes, server_proc_ref, log_callback=None):
        super().__init__()
        self.urls = urls
        self.topic = topic
        self.mode = mode
        self.tavily_key = tavily_key
        self.llama_url = llama_url
        self.llama_exe = llama_exe
        self.gguf_model = gguf_model
        self.ngl = ngl
        self.context = context
        self.target_words = target_words
        self.target_minutes = target_minutes
        self.server_proc_ref = server_proc_ref
        self.log_callback = log_callback

    def run(self):
        try:
            llama = LlamaServer(self.llama_url)
            if not llama.health(timeout=1.5):
                if not self.gguf_model or not os.path.isfile(self.gguf_model):
                    raise RuntimeError(
                        f"llama-server is not running at {self.llama_url} and no valid GGUF model file was selected.\n\n"
                        "Please click 'Browse GGUF...' to select your model file."
                    )
                if not self.llama_exe or not os.path.isfile(self.llama_exe):
                    raise RuntimeError(
                        f"llama-server executable not found at: '{self.llama_exe}'.\n\n"
                        "Please click 'Browse EXE...' to select llama-server.exe."
                    )

                self.progress.emit("Launching local llama-server with GGUF model...")
                if self.log_callback:
                    self.log_callback(f"[ScriptMaker] Auto-starting llama-server on {self.llama_url}...")
                    self.log_callback(f"[ScriptMaker] Model: {self.gguf_model}")

                proc = LlamaServerProcess(
                    exe_path=self.llama_exe,
                    model_path=self.gguf_model,
                    port=8080,
                    ngl=self.ngl,
                    context=self.context,
                    parallel=1,
                    flash_attention=True,
                    log_callback=self.log_callback,
                )
                proc.start()
                self.server_proc_ref[0] = proc

                ready = llama.wait_until_ready(timeout_sec=90, progress_cb=self.progress.emit)
                if not ready:
                    raise RuntimeError(
                        "llama-server process started but failed to become ready within 90 seconds.\n"
                        "Check the 'Activity & Server Logs' tab for details."
                    )
                if self.log_callback:
                    self.log_callback("[ScriptMaker] Server is ready! Starting research and script generation...")

            result = generate(
                self.urls,
                self.topic,
                self.mode,
                self.tavily_key,
                self.llama_url,
                progress=self.progress.emit,
                on_stream=self.stream_token.emit,
                target_words=self.target_words,
                target_minutes=self.target_minutes,
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScriptMaker — Local AI & YouTube Script Generator")
        self.resize(1180, 880)

        self.icon_path = get_icon_path()
        if self.icon_path:
            self.setWindowIcon(QIcon(self.icon_path))

        self.result = None
        self.worker = None
        self.wait_thread = None
        self.server_proc_ref = [None]

        # Smooth token streaming buffer to prevent UI locking
        self.token_buffer = {"brief": [], "script_a": [], "script_b": []}
        self.stream_timer = QTimer(self)
        self.stream_timer.setInterval(35)
        self.stream_timer.timeout.connect(self.flush_stream_buffer)
        self.stream_timer.start()

        self.log_bridge = ServerLogBridge()
        self.log_bridge.log_message.connect(self.append_log)

        self.config = load_config()

        central = QWidget()
        root = QVBoxLayout(central)

        # Header with App Logo
        header_layout = QHBoxLayout()
        if self.icon_path:
            logo_lbl = QLabel()
            pix = QPixmap(self.icon_path).scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            header_layout.addWidget(logo_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title = QLabel("<h1 style='margin:0; padding:0;'>ScriptMaker</h1>")
        title_vbox.addWidget(title)
        title_vbox.addWidget(
            QLabel(
                "Paste source links. ScriptMaker researches them and generates grounded script versions locally."
            )
        )
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        root.addLayout(header_layout)

        # Local LLM Server & Model Settings Group
        model_group = QGroupBox("Local GGUF Model & Server Settings")
        model_layout = QVBoxLayout(model_group)

        # GGUF Model Path
        gguf_layout = QHBoxLayout()
        gguf_layout.addWidget(QLabel("GGUF Model Path:"))
        saved_gguf = self.config.get("gguf_model_path", "")
        default_gguf = saved_gguf if (saved_gguf and os.path.exists(saved_gguf)) else find_default_gguf_model()
        self.gguf_path_input = QLineEdit(default_gguf)
        self.gguf_path_input.setPlaceholderText("Select a .gguf model file from your computer...")
        gguf_layout.addWidget(self.gguf_path_input)

        browse_gguf_btn = QPushButton("Browse GGUF...")
        browse_gguf_btn.clicked.connect(self.browse_gguf_model)
        gguf_layout.addWidget(browse_gguf_btn)
        model_layout.addLayout(gguf_layout)

        # llama-server.exe Path
        exe_layout = QHBoxLayout()
        exe_layout.addWidget(QLabel("llama-server.exe Path:"))
        saved_exe = self.config.get("llama_exe_path", "")
        default_exe = saved_exe if (saved_exe and os.path.exists(saved_exe)) else find_llama_server_exe()
        self.exe_path_input = QLineEdit(default_exe)
        self.exe_path_input.setPlaceholderText("Path to llama-server.exe binary...")
        exe_layout.addWidget(self.exe_path_input)

        browse_exe_btn = QPushButton("Browse EXE...")
        browse_exe_btn.clicked.connect(self.browse_llama_exe)
        exe_layout.addWidget(browse_exe_btn)
        model_layout.addLayout(exe_layout)

        # Server controls & URL
        srv_ctrl_layout = QHBoxLayout()

        srv_ctrl_layout.addWidget(QLabel("Server URL:"))
        self.llama_url = QLineEdit(
            self.config.get("llama_url") or os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080")
        )
        self.llama_url.setFixedWidth(180)
        srv_ctrl_layout.addWidget(self.llama_url)

        srv_ctrl_layout.addWidget(QLabel("GPU Layers (ngl):"))
        self.ngl_input = QSpinBox()
        self.ngl_input.setRange(0, 999)
        self.ngl_input.setValue(self.config.get("gpu_layers", 99))
        self.ngl_input.setFixedWidth(70)
        srv_ctrl_layout.addWidget(self.ngl_input)

        srv_ctrl_layout.addWidget(QLabel("Context Size (-c):"))
        self.ctx_input = QSpinBox()
        self.ctx_input.setRange(2048, 131072)
        self.ctx_input.setSingleStep(2048)
        self.ctx_input.setValue(self.config.get("context_size", 16384))
        self.ctx_input.setFixedWidth(90)
        srv_ctrl_layout.addWidget(self.ctx_input)

        self.server_status_lbl = QLabel("🔴 Server Offline")
        self.server_status_lbl.setStyleSheet("font-weight: bold; color: #d9534f; margin-left: 10px;")
        srv_ctrl_layout.addWidget(self.server_status_lbl)

        srv_ctrl_layout.addStretch()

        self.start_server_btn = QPushButton("Start/Restart Server")
        self.start_server_btn.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 4px 10px;")
        self.start_server_btn.clicked.connect(self.start_local_server)
        srv_ctrl_layout.addWidget(self.start_server_btn)

        self.stop_server_btn = QPushButton("Stop Server")
        self.stop_server_btn.clicked.connect(self.stop_local_server)
        srv_ctrl_layout.addWidget(self.stop_server_btn)

        view_logs_btn = QPushButton("View Logs")
        view_logs_btn.clicked.connect(self.focus_logs_tab)
        srv_ctrl_layout.addWidget(view_logs_btn)

        model_layout.addLayout(srv_ctrl_layout)
        root.addWidget(model_group)

        # Topic & URLs
        root.addWidget(QLabel("Topic"))
        self.topic = QLineEdit(self.config.get("last_topic", ""))
        self.topic.setPlaceholderText(
            "e.g. 10 Essential Sci-Fi TV Shows You Need To Watch Before You Die"
        )
        root.addWidget(self.topic)

        root.addWidget(QLabel("Source URLs — one per line"))
        self.urls = QPlainTextEdit()
        self.urls.setPlaceholderText(
            "https://example.com/article-1\n"
            "https://example.com/article-2\n"
            "https://youtube.com/watch?v=..."
        )
        self.urls.setMinimumHeight(110)
        root.addWidget(self.urls)

        # Research & Script Configuration Form
        form = QFormLayout()

        self.research_mode = QComboBox()
        self.research_mode.addItem("Free web research (recommended)", "free")
        self.research_mode.addItem("Supplied sources only", "sources")
        self.research_mode.addItem("Tavily enhanced", "tavily")

        saved_mode = self.config.get("research_mode", "free")
        for i in range(self.research_mode.count()):
            if self.research_mode.itemData(i) == saved_mode:
                self.research_mode.setCurrentIndex(i)
                break

        form.addRow("Research mode", self.research_mode)

        # Target Video Duration & Word Count Selector
        dur_layout = QHBoxLayout()
        self.duration_combo = QComboBox()
        self.duration_combo.addItem("3 Minutes (~420 words - Quick/Short Form)", (3, 420))
        self.duration_combo.addItem("5 Minutes (~700 words - Standard YouTube)", (5, 700))
        self.duration_combo.addItem("8 Minutes (~1,120 words - Mid-Length)", (8, 1120))
        self.duration_combo.addItem("10 Minutes (~1,400 words - Deep Dive)", (10, 1400))
        self.duration_combo.addItem("15 Minutes (~2,100 words - Long-Form Documentary)", (15, 2100))
        self.duration_combo.addItem("20 Minutes (~2,800 words - Extended Video)", (20, 2800))
        self.duration_combo.addItem("Custom Duration...", "custom")

        self.custom_mins_input = QSpinBox()
        self.custom_mins_input.setRange(1, 60)
        self.custom_mins_input.setValue(self.config.get("target_minutes", 5))
        self.custom_mins_input.setSuffix(" mins")
        self.custom_mins_input.setFixedWidth(85)
        self.custom_mins_input.hide()

        self.custom_words_lbl = QLabel("(~700 words)")
        self.custom_words_lbl.setStyleSheet("color: #666;")
        self.custom_words_lbl.hide()

        self.custom_mins_input.valueChanged.connect(self.on_custom_minutes_changed)
        self.duration_combo.currentIndexChanged.connect(self.on_duration_combo_changed)

        saved_mins = self.config.get("target_minutes", 5)
        matched = False
        for i in range(self.duration_combo.count()):
            data = self.duration_combo.itemData(i)
            if isinstance(data, tuple) and data[0] == saved_mins:
                self.duration_combo.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            self.duration_combo.setCurrentIndex(self.duration_combo.count() - 1)
            self.custom_mins_input.setValue(saved_mins)
            self.custom_mins_input.show()
            self.custom_words_lbl.show()

        dur_layout.addWidget(self.duration_combo)
        dur_layout.addWidget(self.custom_mins_input)
        dur_layout.addWidget(self.custom_words_lbl)
        dur_layout.addStretch()

        form.addRow("Target video length", dur_layout)

        self.tavily = QLineEdit(self.config.get("tavily_key") or os.getenv("TAVILY_API_KEY", ""))
        self.tavily.setEchoMode(QLineEdit.Password)
        form.addRow("Tavily API key (optional)", self.tavily)

        root.addLayout(form)

        actions = QHBoxLayout()

        self.generate_btn = QPushButton("RESEARCH + GENERATE")
        self.generate_btn.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #1976d2; color: white; padding: 7px; font-size: 13px; }"
            "QPushButton:hover { background-color: #1565c0; }"
        )
        self.generate_btn.clicked.connect(self.start_generation)
        actions.addWidget(self.generate_btn)

        save_btn = QPushButton("Save Project")
        save_btn.clicked.connect(self.save_project)
        actions.addWidget(save_btn)

        export_btn = QPushButton("Export Scripts")
        export_btn.clicked.connect(self.export_scripts)
        actions.addWidget(export_btn)

        root.addLayout(actions)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        self.status = QLabel("Ready.")
        root.addWidget(self.status)

        self.tabs = QTabWidget()

        self.research_view = QPlainTextEdit()
        self.research_view.setReadOnly(True)
        self.tabs.addTab(self.research_view, "Research Brief")

        self.script_a = QPlainTextEdit()
        self.script_a.setReadOnly(True)
        self.tabs.addTab(self.script_a, "Version A — Documentary")

        self.script_b = QPlainTextEdit()
        self.script_b.setReadOnly(True)
        self.tabs.addTab(self.script_b, "Version B — YouTube")

        self.sources_view = QPlainTextEdit()
        self.sources_view.setReadOnly(True)
        self.tabs.addTab(self.sources_view, "Sources / Search Results")

        # Activity & Server Logs Tab
        self.log_tab = QWidget()
        log_tab_layout = QVBoxLayout(self.log_tab)
        
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Real-Time Research, Pipeline & Server Activity Logs:</b>"))
        log_header.addStretch()
        clear_log_btn = QPushButton("Clear Logs")
        clear_log_btn.clicked.connect(self.clear_logs)
        log_header.addWidget(clear_log_btn)
        log_tab_layout.addLayout(log_header)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #181818; color: #dcdcdc; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }"
        )
        log_tab_layout.addWidget(self.log_view)
        self.tabs.addTab(self.log_tab, "Activity & Server Logs")

        root.addWidget(self.tabs)

        self.setCentralWidget(central)

        # Health monitor timer (Non-blocking)
        self.timer = QTimer(self)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.check_server_health)
        self.timer.start()
        self.check_server_health()

    def on_duration_combo_changed(self):
        data = self.duration_combo.currentData()
        if data == "custom":
            self.custom_mins_input.show()
            self.custom_words_lbl.show()
            self.on_custom_minutes_changed()
        else:
            self.custom_mins_input.hide()
            self.custom_words_lbl.hide()

    def on_custom_minutes_changed(self):
        mins = self.custom_mins_input.value()
        approx_words = int(mins * 140)
        self.custom_words_lbl.setText(f"(~{approx_words} words)")

    def get_target_duration_and_words(self):
        data = self.duration_combo.currentData()
        if isinstance(data, tuple):
            return data[0], data[1]
        mins = self.custom_mins_input.value()
        words = int(mins * 140)
        return mins, words

    def focus_logs_tab(self):
        self.tabs.setCurrentWidget(self.log_tab)

    def clear_logs(self):
        self.log_view.clear()

    def append_log(self, text: str):
        self.log_view.appendPlainText(text)
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()

    def on_research_progress(self, msg: str):
        self.status.setText(msg)
        now = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{now}] {msg}")

    def on_stream_token(self, section: str, token: str):
        if section in self.token_buffer:
            self.token_buffer[section].append(token)

    def flush_stream_buffer(self):
        for section, tokens in self.token_buffer.items():
            if not tokens:
                continue
            chunk = "".join(tokens)
            tokens.clear()
            if section == "brief":
                self.research_view.moveCursor(QTextCursor.End)
                self.research_view.insertPlainText(chunk)
                self.research_view.ensureCursorVisible()
            elif section == "script_a":
                self.script_a.moveCursor(QTextCursor.End)
                self.script_a.insertPlainText(chunk)
                self.script_a.ensureCursorVisible()
            elif section == "script_b":
                self.script_b.moveCursor(QTextCursor.End)
                self.script_b.insertPlainText(chunk)
                self.script_b.ensureCursorVisible()

    def browse_gguf_model(self):
        current = self.gguf_path_input.text().strip()
        dir_hint = os.path.dirname(current) if current and os.path.exists(current) else str(get_app_dir())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local GGUF Model File",
            dir_hint,
            "GGUF Models (*.gguf);;All Files (*.*)",
        )
        if path:
            self.gguf_path_input.setText(path)
            self.save_current_config()

    def browse_llama_exe(self):
        current = self.exe_path_input.text().strip()
        dir_hint = os.path.dirname(current) if current and os.path.exists(current) else str(get_app_dir())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select llama-server.exe Binary",
            dir_hint,
            "Executable Files (*.exe);;All Files (*.*)",
        )
        if path:
            self.exe_path_input.setText(path)
            self.save_current_config()

    def save_current_config(self):
        mins, words = self.get_target_duration_and_words()
        data = {
            "gguf_model_path": self.gguf_path_input.text().strip(),
            "llama_exe_path": self.exe_path_input.text().strip(),
            "llama_url": self.llama_url.text().strip(),
            "gpu_layers": self.ngl_input.value(),
            "context_size": self.ctx_input.value(),
            "target_minutes": mins,
            "target_words": words,
            "research_mode": self.research_mode.currentData(),
            "tavily_key": self.tavily.text().strip(),
            "last_topic": self.topic.text().strip(),
        }
        save_config(data)

    def check_server_health(self):
        # Do not perform blocking network calls if generation worker is running
        if self.worker and self.worker.isRunning():
            self.server_status_lbl.setText("🟢 Server Generating...")
            self.server_status_lbl.setStyleSheet("font-weight: bold; color: #5cb85c; margin-left: 10px;")
            return

        url = self.llama_url.text().strip()
        llama = LlamaServer(url)
        if llama.health(timeout=0.6):
            self.server_status_lbl.setText(f"🟢 Server Online ({url})")
            self.server_status_lbl.setStyleSheet("font-weight: bold; color: #5cb85c; margin-left: 10px;")
        else:
            if self.wait_thread and self.wait_thread.isRunning():
                self.server_status_lbl.setText("🟡 Starting Server (Loading Model)...")
                self.server_status_lbl.setStyleSheet("font-weight: bold; color: #f0ad4e; margin-left: 10px;")
            else:
                self.server_status_lbl.setText("🔴 Server Offline")
                self.server_status_lbl.setStyleSheet("font-weight: bold; color: #d9534f; margin-left: 10px;")

    def start_local_server(self):
        self.save_current_config()
        exe = self.exe_path_input.text().strip()
        gguf = self.gguf_path_input.text().strip()

        if not os.path.isfile(exe):
            QMessageBox.warning(self, "Invalid llama-server EXE", f"llama-server.exe not found at:\n{exe}\n\nPlease click 'Browse EXE...' to select it.")
            return

        if not os.path.isfile(gguf):
            QMessageBox.warning(self, "Invalid GGUF Model", f"GGUF model file not found at:\n{gguf}\n\nPlease click 'Browse GGUF...' to select a valid .gguf model file.")
            return

        if self.server_proc_ref[0]:
            self.append_log("[ScriptMaker] Stopping existing server process...")
            self.server_proc_ref[0].stop()
            self.server_proc_ref[0] = None

        # Automatically focus logs tab so the user sees live output
        self.focus_logs_tab()

        now = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"\n[{now}] [ScriptMaker] Launching local llama-server...")
        self.append_log(f"[{now}] [ScriptMaker] Binary: {exe}")
        self.append_log(f"[{now}] [ScriptMaker] Model:  {gguf}")
        self.append_log(f"[{now}] [ScriptMaker] GPU offload layers (ngl): {self.ngl_input.value()} | Context: {self.ctx_input.value()}")
        self.append_log("-" * 65)

        try:
            self.status.setText("Starting local LLM server (loading model into memory)...")
            self.server_status_lbl.setText("🟡 Starting Server (Loading Model)...")
            self.server_status_lbl.setStyleSheet("font-weight: bold; color: #f0ad4e; margin-left: 10px;")
            
            proc = LlamaServerProcess(
                exe_path=exe,
                model_path=gguf,
                port=8080,
                ngl=self.ngl_input.value(),
                context=self.ctx_input.value(),
                parallel=1,
                flash_attention=True,
                log_callback=self.log_bridge.log_message.emit,
            )
            proc.start()
            self.server_proc_ref[0] = proc

            # Monitor startup in background thread
            self.wait_thread = ServerWaitThread(self.llama_url.text().strip(), timeout_sec=90)
            self.wait_thread.progress.connect(self.status.setText)
            self.wait_thread.ready.connect(self.on_server_startup_result)
            self.wait_thread.start()

        except Exception as exc:
            self.append_log(f"[ScriptMaker ERROR] {exc}")
            QMessageBox.critical(self, "Error Starting Server", str(exc))

    def on_server_startup_result(self, is_ready: bool):
        now = datetime.now().strftime("%H:%M:%S")
        if is_ready:
            self.status.setText("Local AI server is online and ready.")
            self.append_log(f"\n[{now}] [ScriptMaker SUCCESS] Local AI Server is ONLINE and ready at {self.llama_url.text().strip()}!\n")
            self.check_server_health()
        else:
            self.status.setText("Server failed to become ready in time.")
            self.append_log(f"\n[{now}] [ScriptMaker WARNING] Server did not report ready within 90 seconds. Check logs above.\n")
            self.check_server_health()

    def stop_local_server(self):
        if self.server_proc_ref[0]:
            self.server_proc_ref[0].stop()
            self.server_proc_ref[0] = None
            now = datetime.now().strftime("%H:%M:%S")
            self.append_log(f"[{now}] [ScriptMaker] Local server stopped.")
            self.status.setText("Local server stopped.")
            self.check_server_health()
        else:
            QMessageBox.information(self, "Info", "No server process managed by ScriptMaker is currently running.")

    def start_generation(self):
        self.save_current_config()

        topic = self.topic.text().strip()
        urls = normalize_urls(self.urls.toPlainText())
        mode = self.research_mode.currentData()
        target_mins, target_words = self.get_target_duration_and_words()

        if not topic:
            QMessageBox.warning(self, "Missing topic", "Please enter a topic.")
            return

        if not urls:
            QMessageBox.warning(
                self,
                "Missing URLs",
                "Please add at least one source URL.",
            )
            return

        if mode == "tavily" and not self.tavily.text().strip():
            QMessageBox.warning(
                self,
                "Tavily key required",
                "Tavily mode needs an API key. Use Free web research instead if you want no API key.",
            )
            return

        # Clear previous results and stream buffers
        self.token_buffer = {"brief": [], "script_a": [], "script_b": []}
        self.research_view.clear()
        self.script_a.clear()
        self.script_b.clear()
        self.sources_view.clear()

        self.generate_btn.setEnabled(False)
        self.progress_bar.show()

        now = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"\n[{now}] [ScriptMaker] ===== STARTING RESEARCH & GENERATION =====")
        self.append_log(f"[{now}] [ScriptMaker] Topic: {topic}")
        self.append_log(f"[{now}] [ScriptMaker] Target Duration: {target_mins} mins (~{target_words} words)")
        self.append_log(f"[{now}] [ScriptMaker] Sources count: {len(urls)}")
        self.append_log(f"[{now}] [ScriptMaker] Research Mode: {mode}")

        self.worker = Worker(
            urls=urls,
            topic=topic,
            mode=mode,
            tavily_key=self.tavily.text().strip(),
            llama_url=self.llama_url.text().strip(),
            llama_exe=self.exe_path_input.text().strip(),
            gguf_model=self.gguf_path_input.text().strip(),
            ngl=self.ngl_input.value(),
            context=self.ctx_input.value(),
            target_words=target_words,
            target_minutes=target_mins,
            server_proc_ref=self.server_proc_ref,
            log_callback=self.log_bridge.log_message.emit,
        )
        self.worker.progress.connect(self.on_research_progress)
        self.worker.stream_token.connect(self.on_stream_token)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.failed.connect(self.on_error)
        self.worker.start()

    def on_done(self, result):
        self.result = result
        self.flush_stream_buffer()
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        self.status.setText("Completed.")
        self.check_server_health()

        brief = result["brief"]
        self.research_view.setPlainText(
            json.dumps(brief, indent=2, ensure_ascii=False)
        )
        self.script_a.setPlainText(result["script_a"])
        self.script_b.setPlainText(result["script_b"])

        sources_text = []
        for source in brief.get("sources", []):
            sources_text.append(
                f"{source.get('title')}\n"
                f"{source.get('url')}\n"
                f"Status: {'OK' if source.get('fetched_ok') else 'FAILED'}\n"
                f"Error: {source.get('error') or ''}\n"
            )

        for result_item in result.get("web_results", []):
            sources_text.append(
                f"[SEARCH] {result_item.get('title')}\n"
                f"{result_item.get('url')}\n"
            )

        self.sources_view.setPlainText("\n---\n".join(sources_text))
        
        now = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{now}] [ScriptMaker SUCCESS] Research and scripts generated successfully!")
        self.tabs.setCurrentIndex(1)

    def on_error(self, message):
        self.flush_stream_buffer()
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        self.status.setText("Failed.")
        self.check_server_health()
        now = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{now}] [ScriptMaker ERROR] {message}")
        QMessageBox.critical(self, "Generation error", message)

    def save_project(self):
        if not self.result:
            QMessageBox.information(
                self,
                "Nothing to save",
                "Generate a project first.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save project",
            "script_project.json",
            "JSON Files (*.json)",
        )

        if not path:
            return

        mins, words = self.get_target_duration_and_words()
        payload = {
            "topic": self.topic.text().strip(),
            "source_urls": normalize_urls(self.urls.toPlainText()),
            "research_mode": self.research_mode.currentData(),
            "target_minutes": mins,
            "target_words": words,
            **self.result,
        }

        Path(path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.status.setText(f"Saved: {path}")

    def export_scripts(self):
        if not self.result:
            QMessageBox.information(
                self,
                "Nothing to export",
                "Please generate scripts first before exporting.",
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder to Export Scripts",
        )
        if not folder:
            return

        out_dir = Path(folder)

        # Sanitize topic string for safe Windows filenames (remove : * ? " < > | / \)
        raw_topic = self.topic.text().strip() or "script"
        safe_topic = re.sub(r'[\\/*?:"<>|]', '_', raw_topic)
        safe_topic = re.sub(r'\s+', ' ', safe_topic).strip()[:80]
        if not safe_topic:
            safe_topic = "script"

        doc_file = out_dir / f"{safe_topic}_documentary.md"
        yt_file = out_dir / f"{safe_topic}_youtube.md"
        json_file = out_dir / f"{safe_topic}_research.json"

        try:
            doc_file.write_text(self.result.get("script_a", ""), encoding="utf-8")
            yt_file.write_text(self.result.get("script_b", ""), encoding="utf-8")
            json_file.write_text(
                json.dumps(self.result.get("brief", {}), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            self.status.setText(f"Exported to: {out_dir}")
            now = datetime.now().strftime("%H:%M:%S")
            self.append_log(f"[{now}] [ScriptMaker] Exported 3 files to {out_dir.resolve()}")

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Export Successful")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(
                f"Successfully exported scripts and research to:\n{out_dir}\n\n"
                f"• {doc_file.name}\n"
                f"• {yt_file.name}\n"
                f"• {json_file.name}"
            )
            open_folder_btn = msg_box.addButton("Open Folder", QMessageBox.ActionRole)
            msg_box.addButton(QMessageBox.Ok)
            msg_box.exec()

            if msg_box.clickedButton() == open_folder_btn:
                try:
                    os.startfile(str(out_dir))
                except Exception:
                    pass

        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Failed to write export files:\n{exc}")

    def closeEvent(self, event):
        self.save_current_config()
        if self.server_proc_ref[0]:
            self.server_proc_ref[0].stop()
            self.server_proc_ref[0] = None
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
