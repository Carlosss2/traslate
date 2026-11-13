#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traductor Voz a Lengua de Señas Chiapaneca / LSM
Aplicación de escritorio con PyQt6
"""

import sys
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    sr = None
    SR_AVAILABLE = False

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLabel, QTextEdit,
                            QFrame, QSplitter, QTabWidget, QListWidget,
                            QComboBox, QMessageBox, QDialog, QLineEdit,
                            QFormLayout, QGroupBox, QProgressBar, QToolBar,
                            QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import (QFont, QPixmap, QAction, QKeySequence, QShortcut,
                         QFontMetrics, QMovie)


def resource_base():
    """Carpeta donde viven los recursos, tanto en desarrollo como empaquetada.

    PyInstaller crea una carpeta temporal (`_MEIPASS`) en los builds de un solo
    archivo y una carpeta `_internal` en los builds de carpeta. Usar esta
    función evita depender del directorio desde el que se abre el .exe.
    """
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def resource_path(*parts):
    return resource_base().joinpath(*parts)


# --- Soporte de FLAC ---------------------------------------------------------
# SpeechRecognition convierte el audio a FLAC antes de enviarlo a Google. Si no
# encuentra el comando `flac` en el PATH usa los binarios que trae incluidos,
# pero el de macOS es x86_64 y en Apple Silicon falla con:
#   [Errno 86] Bad CPU type in executable: .../speech_recognition/flac-mac
# La librería comprueba `shutil.which("flac")` antes que sus binarios internos,
# así que basta con exponer una instalación nativa en el PATH.

def _flac_candidates():
    """Rutas habituales donde puede estar instalado el ejecutable `flac`."""
    candidates = []
    if getattr(sys, 'frozen', False):
        # En el .exe empaquetado puede incluirse un flac.exe en bin/
        candidates.append(str(resource_path("bin")))
        candidates.append(str(Path(sys.executable).resolve().parent / "bin"))
    if sys.platform == "darwin":
        # Homebrew (Apple Silicon e Intel) y MacPorts
        candidates += ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
    elif os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            # Enlaces que crea `winget install --id Xiph.FLAC`
            candidates.append(os.path.join(local_appdata, "Microsoft", "WinGet", "Links"))
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
            base = os.environ.get(variable)
            if base:
                candidates += [os.path.join(base, "FLAC"), os.path.join(base, "flac")]
        chocolatey = os.environ.get("ChocolateyInstall") or r"C:\ProgramData\chocolatey"
        candidates.append(os.path.join(chocolatey, "bin"))
        candidates.append(os.path.join(os.path.expanduser("~"), "scoop", "shims"))
    else:
        candidates += ["/usr/local/bin", "/usr/bin", "/snap/bin"]
    return candidates


def _flac_works(executable):
    """Devuelve True si el binario responde a `--version`."""
    try:
        kwargs = {}
        if os.name == "nt":
            # Evitar que se abra una consola al lanzar el proceso
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            timeout=5,
            **kwargs,
        )
        return result.returncode == 0
    except Exception:
        return False


def _ensure_flac_in_path():
    """Añade al PATH una instalación de FLAC que funcione.

    No modifica nada si `flac` ya está disponible. Devuelve True si al final hay
    un FLAC utilizable y False en caso contrario. Nunca lanza excepciones, para
    no impedir el arranque de la aplicación.
    """
    try:
        found = shutil.which("flac")
        if found and _flac_works(found):
            return True

        for directory in _flac_candidates():
            executable = os.path.join(directory, "flac.exe" if os.name == "nt" else "flac")
            if not (os.path.isfile(executable) and os.access(executable, os.X_OK)):
                continue
            if not _flac_works(executable):
                continue
            current = os.environ.get("PATH", "")
            os.environ["PATH"] = directory + (os.pathsep + current if current else "")
            return True
        return False
    except Exception:
        return False


def _is_flac_error(error):
    """Detecta el fallo típico de FLAC (binario Intel en Apple Silicon)."""
    message = str(error).lower()
    return "flac" in message or "bad cpu type" in message


class VoiceRecognitionThread(QThread):
    """Hilo para reconocimiento de voz"""
    text_recognized = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Estos atributos deben existir siempre, aunque la inicialización falle,
        # para que stop() y run() puedan usarlos sin lanzar AttributeError.
        self.recognizer = None
        self.microphone = None
        self.running = False
        self.init_error = None

        if not SR_AVAILABLE:
            self.init_error = "speech_recognition no está instalado"
            return

        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            # Ajustar ruido ambiente
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            # No se puede emitir aquí: las señales todavía no están conectadas.
            # El error se emite desde run(), que sí corre en el hilo de trabajo.
            self.init_error = str(e)
            self.recognizer = None
            self.microphone = None

    def run(self):
        if self.init_error:
            self.error_occurred.emit(self.init_error)
            return
        if self.recognizer is None or self.microphone is None:
            self.error_occurred.emit("Micrófono no disponible")
            return
        self.running = True
        self.status_changed.emit("Escuchando...")

        try:
            with self.microphone as source:
                while self.running:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)
                        self.status_changed.emit("Procesando...")
                        try:
                            text = self.recognizer.recognize_google(audio, language='es-MX')
                            self.text_recognized.emit(text)
                            self.status_changed.emit("Escuchando...")
                        except sr.UnknownValueError:
                            # No se entendió lo que se dijo: seguir escuchando
                            self.status_changed.emit("Sin voz detectada...")
                            continue
                        except sr.RequestError:
                            # Sin conexión o servicio de Google no disponible
                            self.status_changed.emit("Sin conexión con Google...")
                            continue
                        except Exception as e:
                            if _is_flac_error(e):
                                self.error_occurred.emit(
                                    "No se pudo convertir el audio a FLAC.\n\n"
                                    "Instala FLAC nativo en tu sistema:\n"
                                    "  macOS:    brew install flac\n"
                                    "  Windows:  winget install --id Xiph.FLAC\n"
                                    "  Linux:    sudo apt install flac\n\n"
                                    f"Detalle: {e}"
                                )
                            else:
                                self.error_occurred.emit(str(e))
                            break
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        self.status_changed.emit(f"Error: {str(e)[:50]}")
                        break
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.running = False


class SignLanguageTranslator(QMainWindow):
    """Ventana principal del traductor.

    La interfaz está pensada para proyectarse en un salón: la traducción ocupa
    la mayor parte de la pantalla con letras grandes y la seña queda en un panel
    pequeño en la parte inferior.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traductor Voz a Lengua de Señas Chiapaneca - LSM")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 640)

        self.load_config()
        self.load_dictionary()

        self.voice_thread = None
        self.current_queue = []
        self.current_phrase = ""
        self.is_listening = False
        self.is_playing = False
        self.play_index = -1
        self.play_speed = 1.0
        self.font_scale = 1.0
        self.projector_mode = False
        self.sign_movie = None
        self.shortcuts = []

        # Reproducción de la cola con un temporizador: permite pausar,
        # reanudar y saltar de seña sin reiniciar la frase desde el principio.
        self.play_timer = QTimer(self)
        self.play_timer.setSingleShot(True)
        self.play_timer.timeout.connect(self.advance_playback)

        self.init_ui()
        self.apply_theme()
        self.set_phrase("")
        QTimer.singleShot(0, self.fit_phrase_font)

    # ------------------------------------------------------------------ datos
    def load_config(self):
        config_file = resource_path('config.json')
        if not config_file.exists():
            config_file = Path.cwd() / 'config.json'
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {"language": "es-MX", "theme": "light"}

    def load_dictionary(self):
        dictionary_file = resource_path('data', 'diccionario.json')
        if not dictionary_file.exists():
            dictionary_file = Path.cwd() / 'data' / 'diccionario.json'
        try:
            with open(dictionary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.dictionary = data.get('dictionary', {})
                self.alphabet = data.get('alphabet', {})
                self.dict_metadata = data.get('metadata', {})
            self.statusBar().showMessage(f"Diccionario cargado: {len(self.dictionary)} palabras")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el diccionario: {e}")
            self.dictionary = {}
            self.alphabet = {}
            self.dict_metadata = {}

    # -------------------------------------------------------------------- UI
    def init_ui(self):
        self.create_menu()
        self.create_toolbar()
        self.create_shortcuts()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.splitter)

        self.control_panel = self.create_left_panel()
        self.splitter.addWidget(self.control_panel)

        presentation = self.create_right_panel()
        self.splitter.addWidget(presentation)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([360, 1080])

        self.statusBar().showMessage("Listo")

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Archivo")
        exit_action = QAction("Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu("Ver")
        self.projector_action = QAction("Modo proyector (F11)", self)
        self.projector_action.triggered.connect(self.toggle_projector_mode)
        view_menu.addAction(self.projector_action)

        bigger_action = QAction("Aumentar texto", self)
        bigger_action.triggered.connect(lambda: self.change_font_scale(0.1))
        view_menu.addAction(bigger_action)

        smaller_action = QAction("Reducir texto", self)
        smaller_action.triggered.connect(lambda: self.change_font_scale(-0.1))
        view_menu.addAction(smaller_action)

        view_menu.addSeparator()
        clear_action = QAction("Limpiar pantalla", self)
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.clear_display)
        view_menu.addAction(clear_action)

        dict_menu = menubar.addMenu("Diccionario")
        admin_action = QAction("Gestionar diccionario", self)
        admin_action.triggered.connect(self.open_dictionary_manager)
        dict_menu.addAction(admin_action)

        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(self.toolbar)

        mic_action = QAction("Micrófono", self)
        mic_action.triggered.connect(self.toggle_listening)
        self.toolbar.addAction(mic_action)

        test_action = QAction("Simular voz", self)
        test_action.triggered.connect(self.simulate_voice)
        self.toolbar.addAction(test_action)

        self.toolbar.addSeparator()

        dict_action = QAction("Diccionario", self)
        dict_action.triggered.connect(self.open_dictionary_manager)
        self.toolbar.addAction(dict_action)

        self.toolbar.addSeparator()

        projector_tb = QAction("Modo proyector", self)
        projector_tb.triggered.connect(self.toggle_projector_mode)
        self.toolbar.addAction(projector_tb)

    def create_shortcuts(self):
        """Atajos pensados para controlar la app desde el proyector."""
        bindings = [
            ("Space", self.shortcut_toggle_playback),
            ("Left", self.shortcut_previous),
            ("Right", self.shortcut_next),
            ("F11", self.toggle_projector_mode),
            ("Escape", self.shortcut_escape),
            ("Ctrl+L", self.clear_display),
        ]
        for key, callback in bindings:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    # ------------------------------------------------------- panel izquierdo
    def create_left_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        voice_group = QGroupBox("Reconocimiento de voz")
        voice_layout = QVBoxLayout(voice_group)

        self.mic_btn = QPushButton("Iniciar escucha")
        self.mic_btn.setMinimumHeight(56)
        self.mic_btn.setObjectName("primaryButton")
        self.mic_btn.clicked.connect(self.toggle_listening)
        voice_layout.addWidget(self.mic_btn)

        if not SR_AVAILABLE:
            self.mic_btn.setEnabled(False)
            self.mic_btn.setText("Micrófono no disponible")
            warning = QLabel("speech_recognition no está instalado")
            warning.setStyleSheet("color: #b3261e;")
            warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning.setWordWrap(True)
            voice_layout.addWidget(warning)

        self.mic_status = QLabel("Estado: listo")
        self.mic_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mic_status.setObjectName("mutedLabel")
        voice_layout.addWidget(self.mic_status)

        manual_row = QHBoxLayout()
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Escribe una frase...")
        self.manual_input.returnPressed.connect(self.handle_manual_input)
        manual_row.addWidget(self.manual_input, 1)
        manual_btn = QPushButton("Traducir")
        manual_btn.clicked.connect(self.handle_manual_input)
        manual_row.addWidget(manual_btn)
        voice_layout.addLayout(manual_row)

        layout.addWidget(voice_group)

        history_group = QGroupBox("Historial de voz")
        history_layout = QVBoxLayout(history_group)
        self.trans_text = QTextEdit()
        self.trans_text.setReadOnly(True)
        self.trans_text.setPlaceholderText("Aquí se guarda lo que se va reconociendo...")
        self.trans_text.setMaximumHeight(150)
        history_layout.addWidget(self.trans_text)
        self.word_count_label = QLabel("Palabras: 0")
        self.word_count_label.setObjectName("mutedLabel")
        history_layout.addWidget(self.word_count_label)
        layout.addWidget(history_group)

        queue_group = QGroupBox("Cola de reproducción")
        queue_layout = QVBoxLayout(queue_group)
        self.queue_list = QListWidget()
        self.queue_list.setAlternatingRowColors(False)
        self.queue_list.itemDoubleClicked.connect(self.jump_to_item)
        queue_layout.addWidget(self.queue_list, 1)
        self.queue_status = QLabel("Cola vacía")
        self.queue_status.setObjectName("mutedLabel")
        queue_layout.addWidget(self.queue_status)
        layout.addWidget(queue_group, 1)

        return panel

    # ---------------------------------------------------- panel de traducción
    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Tarjeta grande: es lo que se proyecta y debe leerse a distancia.
        translation_card = QFrame()
        translation_card.setObjectName("translationCard")
        translation_card.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(translation_card)
        card_layout.setContentsMargins(28, 20, 28, 24)
        card_layout.setSpacing(6)

        caption = QLabel("TRADUCCIÓN")
        caption.setObjectName("sectionCaption")
        card_layout.addWidget(caption)

        self.phrase_display = QLabel()
        self.phrase_display.setObjectName("phraseDisplay")
        self.phrase_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phrase_display.setWordWrap(True)
        self.phrase_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Ignored evita que una letra gigante cambie el tamaño mínimo de la ventana.
        self.phrase_display.setSizePolicy(QSizePolicy.Policy.Ignored,
                                          QSizePolicy.Policy.Expanding)
        self.phrase_display.setMinimumHeight(120)
        card_layout.addWidget(self.phrase_display, 1)

        layout.addWidget(translation_card, 1)

        # Tarjeta pequeña: seña actual (imagen/GIF o descripción).
        sign_card = QFrame()
        sign_card.setObjectName("signCard")
        sign_card.setMinimumHeight(168)
        sign_card.setMaximumHeight(230)
        sign_layout = QVBoxLayout(sign_card)
        sign_layout.setContentsMargins(16, 10, 16, 12)
        sign_layout.setSpacing(6)

        sign_caption = QLabel("SEÑA ACTUAL")
        sign_caption.setObjectName("sectionCaption")
        sign_layout.addWidget(sign_caption)

        sign_content = QHBoxLayout()
        sign_content.setSpacing(14)

        self.sign_image = QLabel()
        self.sign_image.setObjectName("signImage")
        self.sign_image.setFixedSize(140, 140)
        self.sign_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sign_image.setText("Sin imagen")
        sign_content.addWidget(self.sign_image)

        sign_text_layout = QVBoxLayout()
        sign_text_layout.setSpacing(2)
        self.sign_word = QLabel("-")
        self.sign_word.setObjectName("signWord")
        self.sign_word.setWordWrap(True)
        sign_text_layout.addWidget(self.sign_word)

        self.sign_desc = QLabel("Las señas aparecerán aquí")
        self.sign_desc.setObjectName("signDesc")
        self.sign_desc.setWordWrap(True)
        sign_text_layout.addWidget(self.sign_desc, 1)

        self.sign_meta = QLabel("")
        self.sign_meta.setObjectName("signMeta")
        self.sign_meta.setWordWrap(True)
        sign_text_layout.addWidget(self.sign_meta)

        sign_content.addLayout(sign_text_layout, 1)
        sign_layout.addLayout(sign_content)
        layout.addWidget(sign_card)

        # Controles de reproducción.
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.prev_btn = QPushButton("Anterior")
        self.prev_btn.clicked.connect(self.play_previous)
        self.prev_btn.setEnabled(False)
        controls.addWidget(self.prev_btn)

        self.play_pause_btn = QPushButton("Reproducir")
        self.play_pause_btn.setObjectName("primaryButton")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setMinimumWidth(150)
        controls.addWidget(self.play_pause_btn)

        self.next_btn = QPushButton("Siguiente")
        self.next_btn.clicked.connect(self.play_next)
        self.next_btn.setEnabled(False)
        controls.addWidget(self.next_btn)

        self.stop_btn = QPushButton("Detener")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.stop_btn)

        for button in (self.prev_btn, self.play_pause_btn,
                       self.next_btn, self.stop_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        controls.addStretch()

        controls.addWidget(QLabel("Velocidad"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        controls.addWidget(self.speed_combo)

        controls.addSpacing(16)
        controls.addWidget(QLabel("Texto"))
        font_minus = QPushButton("A-")
        font_minus.clicked.connect(lambda: self.change_font_scale(-0.1))
        font_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        controls.addWidget(font_minus)
        font_plus = QPushButton("A+")
        font_plus.clicked.connect(lambda: self.change_font_scale(0.1))
        font_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        controls.addWidget(font_plus)

        layout.addLayout(controls)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        layout.addWidget(self.progress_bar)

        self.hint_label = QLabel(
            "Espacio: reproducir/pausar   |   Flechas: anterior/siguiente   |   "
            "F11: modo proyector   |   Ctrl+L: limpiar"
        )
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        return panel

    # -------------------------------------------------------------- tipografía
    def _fit_label_font(self, label, text, max_point):
        """Busca el mayor tamaño de letra que quepa en el espacio disponible."""
        if not text:
            return
        rect = label.contentsRect().adjusted(20, 10, -20, -10)
        if rect.width() < 60 or rect.height() < 30:
            return

        low, high = 12, max_point
        best = low
        while low <= high:
            mid = (low + high) // 2
            font = QFont(label.font())
            font.setPointSize(mid)
            font.setBold(True)
            metrics = QFontMetrics(font)
            bounds = metrics.boundingRect(
                rect, Qt.TextFlag.TextWordWrap, text
            )
            if bounds.width() <= rect.width() and bounds.height() <= rect.height():
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        font = QFont(label.font())
        font.setPointSize(max(12, int(best * self.font_scale)))
        font.setBold(True)
        label.setFont(font)

    def fit_phrase_font(self):
        if self.current_phrase:
            self._fit_label_font(self.phrase_display, self.current_phrase, 240)
        else:
            self._fit_label_font(self.phrase_display, "Esperando voz", 72)

    def set_phrase(self, text):
        text = (text or "").strip()
        self.current_phrase = text
        if text:
            self.phrase_display.setStyleSheet("")
            self.phrase_display.setText(text)
            self.phrase_display.setToolTip(text)
            self._fit_label_font(self.phrase_display, text, 240)
        else:
            self.phrase_display.setStyleSheet("color: #b0b0b0;")
            self.phrase_display.setText("Esperando voz")
            self.phrase_display.setToolTip("")
            self._fit_label_font(self.phrase_display, "Esperando voz", 72)
        QTimer.singleShot(0, self.fit_phrase_font)

    def change_font_scale(self, delta):
        self.font_scale = max(0.6, min(1.8, self.font_scale + delta))
        self.fit_phrase_font()
        self.statusBar().showMessage(
            f"Tamaño del texto: {int(round(self.font_scale * 100))}%"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.fit_phrase_font)

    # --------------------------------------------------------------- voz
    def toggle_listening(self):
        if not SR_AVAILABLE:
            QMessageBox.warning(
                self, "No disponible",
                "SpeechRecognition no está instalado.\n"
                "Puedes usar el campo de texto o el simulador de voz."
            )
            return
        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        try:
            self.voice_thread = VoiceRecognitionThread()
            self.voice_thread.text_recognized.connect(self.process_recognized_text)
            self.voice_thread.status_changed.connect(self.update_mic_status)
            self.voice_thread.error_occurred.connect(self.handle_voice_error)
            self.voice_thread.start()
            self.is_listening = True
            self.mic_btn.setText("Detener escucha")
            self.mic_status.setText("Estado: escuchando...")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar el reconocimiento: {e}")

    def stop_listening(self):
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.wait()
        self.is_listening = False
        self.mic_btn.setText("Iniciar escucha")
        self.mic_status.setText("Estado: listo")

    def update_mic_status(self, status):
        self.mic_status.setText(f"Estado: {status}")

    def handle_voice_error(self, error):
        self.mic_status.setText(f"Error: {error}")
        self.is_listening = False
        self.mic_btn.setText("Iniciar escucha")
        QMessageBox.warning(
            self, "Error de micrófono",
            f"Error: {error}\n\nUsa el campo de texto como alternativa."
        )

    def handle_manual_input(self):
        text = self.manual_input.text().strip()
        if not text:
            return
        self.log_history("Escrito", text)
        self.handle_new_phrase(text)
        self.manual_input.clear()

    def process_recognized_text(self, text):
        self.log_history("Voz", text)
        self.handle_new_phrase(text)

    def log_history(self, source, text):
        stamp = datetime.now().strftime("%H:%M")
        self.trans_text.append(f"[{stamp}] {source}: {text}")

    def handle_new_phrase(self, text):
        text = (text or "").strip()
        if not text:
            return
        self.set_phrase(text)
        self.word_count_label.setText(f"Palabras: {len(text.split())}")
        self.process_text_to_signs(text)

    # ------------------------------------------------------- cola de señas
    def process_text_to_signs(self, text):
        words = text.lower().split()
        self.play_timer.stop()
        self.is_playing = False
        self.play_index = -1
        self.current_queue = []

        i = 0
        while i < len(words):
            word = words[i].strip('.,!?;:()[]{}"\'')
            if not word:
                i += 1
                continue

            if i < len(words) - 1:
                two_word = word + " " + words[i + 1].strip('.,!?;:()[]{}"\'')
                if two_word in self.dictionary:
                    self.current_queue.append({
                        'word': two_word,
                        'type': 'sign',
                        'data': self.dictionary[two_word],
                        'original': two_word
                    })
                    i += 2
                    continue

            if word in self.dictionary:
                self.current_queue.append({
                    'word': word,
                    'type': 'sign',
                    'data': self.dictionary[word],
                    'original': word
                })
            else:
                for letter in word:
                    if letter in self.alphabet:
                        self.current_queue.append({
                            'word': letter.upper(),
                            'type': 'letter',
                            'data': {
                                'file': self.alphabet[letter]['file'],
                                'description': f'Letra {letter.upper()}'
                            },
                            'original': letter
                        })
            i += 1

        self.update_queue_display()
        if self.current_queue:
            self.enable_playback_controls()
            self.start_playback()
        else:
            self.disable_playback_controls()
            self.reset_sign_panel("No se encontraron señas para esta frase")

    def update_queue_display(self):
        self.queue_list.clear()
        for i, item in enumerate(self.current_queue):
            tipo = "SEÑA" if item['type'] == 'sign' else "LETRA"
            region = item['data'].get('region', 'N/A') if item['type'] == 'sign' else 'DACTIL'
            self.queue_list.addItem(f"{i + 1}. [{tipo}] {item['word']} ({region})")
        self.queue_status.setText(f"Cola: {len(self.current_queue)} elementos")

    def enable_playback_controls(self):
        self.prev_btn.setEnabled(True)
        self.play_pause_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.play_pause_btn.setText("Reproducir")

    def disable_playback_controls(self):
        self.prev_btn.setEnabled(False)
        self.play_pause_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.play_pause_btn.setText("Reproducir")

    # ------------------------------------------------------- reproducción
    def start_playback(self):
        if not self.current_queue:
            return
        self.play_index = 0
        self.is_playing = True
        self.play_pause_btn.setText("Pausar")
        self.show_current_item()
        self.schedule_next()

    def schedule_next(self):
        if not self.is_playing or not (0 <= self.play_index < len(self.current_queue)):
            return
        item = self.current_queue[self.play_index]
        duration = 2500 if item['type'] == 'sign' else 1200
        interval = max(350, int(duration / self.play_speed))
        self.play_timer.start(interval)

    def advance_playback(self):
        if not self.is_playing:
            return
        if self.play_index + 1 >= len(self.current_queue):
            self.finish_playback()
            return
        self.play_index += 1
        self.show_current_item()
        self.schedule_next()

    def show_current_item(self):
        if not (0 <= self.play_index < len(self.current_queue)):
            return
        item = self.current_queue[self.play_index]
        self.display_sign(item, self.play_index)
        total = len(self.current_queue)
        self.progress_bar.setValue(int((self.play_index + 1) / total * 100))
        self.queue_list.setCurrentRow(self.play_index)

    def display_sign(self, item, index):
        region = item['data'].get('region', 'nacional')
        desc = item['data'].get('description', item['word'])
        total = len(self.current_queue)

        self.sign_word.setText(item['word'].upper())
        self.sign_desc.setText(desc)

        if item['type'] == 'sign':
            tipo = "Seña completa"
            variante = "Variante Chiapas" if region == 'chiapas' else "Nacional LSM"
            self.sign_meta.setText(f"{tipo}  |  {variante}  |  {index + 1} de {total}")
        else:
            self.sign_meta.setText(f"Deletreo dactilológico LSM  |  {index + 1} de {total}")

        self.load_sign_asset(item)

    def toggle_playback(self):
        if not self.current_queue:
            return
        if self.is_playing:
            self.pause_playback()
        else:
            if not (0 <= self.play_index < len(self.current_queue)):
                self.play_index = 0
            self.is_playing = True
            self.play_pause_btn.setText("Pausar")
            self.show_current_item()
            self.schedule_next()

    def pause_playback(self):
        self.is_playing = False
        self.play_timer.stop()
        self.play_pause_btn.setText("Reproducir")

    def play_previous(self):
        if not self.current_queue:
            return
        self.play_index = max(0, self.play_index - 1)
        self.show_current_item()
        if self.is_playing:
            self.schedule_next()
        else:
            self.play_pause_btn.setText("Reproducir")

    def play_next(self):
        if not self.current_queue:
            return
        if self.play_index + 1 >= len(self.current_queue):
            self.finish_playback()
            return
        self.play_index += 1
        self.show_current_item()
        if self.is_playing:
            self.schedule_next()
        else:
            self.play_pause_btn.setText("Reproducir")

    def stop_playback(self):
        self.play_timer.stop()
        self.is_playing = False
        self.play_index = -1
        self.progress_bar.setValue(0)
        self.play_pause_btn.setText("Reproducir")
        self.queue_list.clearSelection()
        self.reset_sign_panel("Reproducción detenida")

    def finish_playback(self):
        self.play_timer.stop()
        self.is_playing = False
        self.play_index = -1
        self.progress_bar.setValue(100)
        self.play_pause_btn.setText("Reproducir")
        self.queue_list.clearSelection()
        self.stop_sign_movie()
        self.sign_image.clear()
        self.sign_image.setText("Fin")
        self.sign_word.setText("Traducción completada")
        self.sign_desc.setText("La frase terminó de reproducirse.")
        self.sign_meta.setText(f"{len(self.current_queue)} elementos mostrados")

    def jump_to_item(self, list_item):
        row = self.queue_list.row(list_item)
        if 0 <= row < len(self.current_queue):
            self.play_index = row
            self.show_current_item()
            if self.is_playing:
                self.schedule_next()
            else:
                self.play_pause_btn.setText("Reproducir")

    def change_speed(self, text):
        try:
            self.play_speed = float(text.replace('x', ''))
        except ValueError:
            self.play_speed = 1.0
        if self.is_playing:
            self.schedule_next()

    # ------------------------------------------------------- recursos/limpia
    def _asset_path(self, item):
        filename = (item.get('data') or {}).get('file')
        if not filename:
            return None
        if item['type'] == 'sign':
            folder = self.config.get('signs_dir', 'data/señas')
        else:
            folder = self.config.get('alphabet_dir', 'data/alfabeto')
        path = resource_path(folder, filename)
        return path if path.exists() else None

    def stop_sign_movie(self):
        if self.sign_movie is not None:
            self.sign_movie.stop()
            self.sign_movie = None

    def load_sign_asset(self, item):
        self.stop_sign_movie()
        self.sign_image.clear()
        self.sign_image.setFont(QFont(self.sign_image.font().family(), 46, QFont.Weight.Bold))

        path = self._asset_path(item)
        if path is not None:
            if path.suffix.lower() == '.gif':
                movie = QMovie(str(path))
                if movie.isValid():
                    movie.jumpToFrame(0)
                    frame_size = movie.currentImage().size()
                    if frame_size.isValid():
                        movie.setScaledSize(frame_size.scaled(
                            self.sign_image.size(),
                            Qt.AspectRatioMode.KeepAspectRatio
                        ))
                    self.sign_image.setMovie(movie)
                    movie.start()
                    self.sign_movie = movie
                    return
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.sign_image.setPixmap(pixmap.scaled(
                    self.sign_image.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                return

        if item['type'] == 'letter':
            self.sign_image.setText(item['word'].upper())
        else:
            self.sign_image.setText("Sin imagen")

    def reset_sign_panel(self, message="Las señas aparecerán aquí"):
        self.stop_sign_movie()
        self.sign_image.clear()
        self.sign_image.setFont(QFont(self.sign_image.font().family(), 13))
        self.sign_image.setText("Sin imagen")
        self.sign_word.setText("-")
        self.sign_desc.setText(message)
        self.sign_meta.setText("")

    def clear_display(self):
        self.play_timer.stop()
        self.is_playing = False
        self.play_index = -1
        self.current_queue = []
        self.queue_list.clear()
        self.queue_status.setText("Cola vacía")
        self.progress_bar.setValue(0)
        self.disable_playback_controls()
        self.reset_sign_panel()
        self.set_phrase("")
        self.word_count_label.setText("Palabras: 0")
        self.statusBar().showMessage("Pantalla limpia")

    # -------------------------------------------------------- atajos teclado
    def _typing(self):
        widget = QApplication.focusWidget()
        return isinstance(widget, QLineEdit) or (
            isinstance(widget, QTextEdit) and not widget.isReadOnly()
        )

    def shortcut_toggle_playback(self):
        if not self._typing():
            self.toggle_playback()

    def shortcut_previous(self):
        if not self._typing():
            self.play_previous()

    def shortcut_next(self):
        if not self._typing():
            self.play_next()

    def shortcut_escape(self):
        if self.projector_mode:
            self.toggle_projector_mode()

    # ------------------------------------------------------ modo proyector
    def toggle_projector_mode(self):
        self.projector_mode = not self.projector_mode
        if self.projector_mode:
            self.control_panel.setVisible(False)
            self.menuBar().setVisible(False)
            self.toolbar.setVisible(False)
            self.statusBar().setVisible(False)
            self.projector_action.setText("Salir del modo proyector (Esc)")
            self.showFullScreen()
        else:
            self.control_panel.setVisible(True)
            self.menuBar().setVisible(True)
            self.toolbar.setVisible(True)
            self.statusBar().setVisible(True)
            self.projector_action.setText("Modo proyector (F11)")
            self.showNormal()
        QTimer.singleShot(50, self.fit_phrase_font)

    # ---------------------------------------------------------- simulador
    def simulate_voice(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Simulador de voz")
        dialog.resize(520, 440)
        layout = QVBoxLayout(dialog)

        title = QLabel("Selecciona una frase o escribe la tuya:")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        phrases = [
            "Hola, buenos días amigo",
            "Gracias por tu ayuda",
            "¿Cómo estás?",
            "Sí, por favor necesito ayuda",
            "Chiapas es mi tierra",
            "Bienvenido a mi comunidad",
            "hola como estas",
            "buenos dias amigo"
        ]

        for p in phrases:
            btn = QPushButton(p)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked=False, text=p: self.simulate_and_close(dialog, text))
            layout.addWidget(btn)

        layout.addSpacing(8)
        layout.addWidget(QLabel("O escribe tu propia frase:"))
        self.sim_input = QLineEdit()
        self.sim_input.setMinimumHeight(38)
        self.sim_input.returnPressed.connect(
            lambda: self.simulate_and_close(dialog, self.sim_input.text())
        )
        layout.addWidget(self.sim_input)

        sim_btn = QPushButton("Traducir")
        sim_btn.setObjectName("primaryButton")
        sim_btn.setMinimumHeight(42)
        sim_btn.clicked.connect(
            lambda: self.simulate_and_close(dialog, self.sim_input.text())
        )
        layout.addWidget(sim_btn)

        dialog.exec()

    def simulate_and_close(self, dialog, text):
        text = (text or "").strip()
        if text:
            self.log_history("Simulado", text)
            self.handle_new_phrase(text)
        dialog.close()

    # --------------------------------------------------------- diccionario
    def open_dictionary_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Gestor de diccionario")
        dialog.resize(860, 620)
        layout = QVBoxLayout(dialog)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        explore_tab = QWidget()
        explore_layout = QVBoxLayout(explore_tab)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        search_input = QLineEdit()
        search_layout.addWidget(search_input)
        filter_combo = QComboBox()
        filter_combo.addItems(["Todas", "Chiapas", "Nacional"])
        search_layout.addWidget(filter_combo)
        explore_layout.addLayout(search_layout)

        dict_list = QListWidget()
        count = 0
        for word, data in sorted(self.dictionary.items()):
            if count >= 150:
                break
            region = "CHIAPAS" if data.get('region') == 'chiapas' else "NACIONAL"
            dict_list.addItem(f"{word} [{region}] - {data.get('description', '')}")
            count += 1
        explore_layout.addWidget(dict_list)
        explore_layout.addWidget(QLabel(f"Mostrando {count} de {len(self.dictionary)} palabras"))

        tabs.addTab(explore_tab, "Explorar")

        add_tab = QWidget()
        add_layout = QFormLayout(add_tab)
        word_input = QLineEdit()
        region_combo = QComboBox()
        region_combo.addItems(["chiapas", "nacional"])
        file_input = QLineEdit()
        desc_input = QLineEdit()

        add_layout.addRow("Palabra/Frase:", word_input)
        add_layout.addRow("Región:", region_combo)
        add_layout.addRow("Archivo de seña:", file_input)
        add_layout.addRow("Descripción:", desc_input)

        save_btn = QPushButton("Guardar seña")
        save_btn.clicked.connect(
            lambda: self.save_new_sign(
                word_input.text(), region_combo.currentText(),
                file_input.text(), desc_input.text(), dialog
            )
        )
        add_layout.addRow(save_btn)

        tabs.addTab(add_tab, "Agregar")

        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        chiapas_count = sum(1 for v in self.dictionary.values() if v.get('region') == 'chiapas')
        nacional_count = len(self.dictionary) - chiapas_count

        stats_layout.addWidget(QLabel(f"Total de palabras: {len(self.dictionary)}"))
        stats_layout.addWidget(QLabel(f"Palabras con variante Chiapas: {chiapas_count}"))
        stats_layout.addWidget(QLabel(f"Palabras Nacional LSM: {nacional_count}"))
        stats_layout.addWidget(QLabel(f"Letras en alfabeto dactilológico: {len(self.alphabet)}"))
        stats_layout.addStretch()

        tabs.addTab(stats_tab, "Estadísticas")

        dialog.exec()

    def save_new_sign(self, word, region, file, desc, dialog):
        if word and file:
            self.dictionary[word.lower()] = {
                "type": "sign",
                "region": region,
                "category": "personalizado",
                "file": file,
                "description": desc or word
            }
            QMessageBox.information(dialog, "Éxito", "Seña guardada correctamente")
            self.statusBar().showMessage(
                f"Diccionario actualizado: {len(self.dictionary)} palabras"
            )
        else:
            QMessageBox.warning(dialog, "Error", "Palabra y archivo son obligatorios")

    # ------------------------------------------------------------- estilo
    def apply_theme(self):
        """Tema único claro y de alto contraste, ideal para proyector."""
        self.setStyleSheet("""
            QMainWindow, QWidget, QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d5d5d5;
                border-radius: 10px;
                margin-top: 16px;
                padding: 10px 10px 10px 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                color: #000000;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #c6c6c6;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #ececec; }
            QPushButton:pressed { background-color: #dedede; }
            QPushButton:disabled { color: #a0a0a0; border-color: #e4e4e4; }
            QPushButton#primaryButton {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid #000000;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover { background-color: #222222; }
            QPushButton#primaryButton:pressed { background-color: #333333; }
            QPushButton#primaryButton:disabled {
                background-color: #d9d9d9;
                color: #8a8a8a;
                border-color: #d9d9d9;
            }
            QLineEdit, QTextEdit, QListWidget, QComboBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #c6c6c6;
                border-radius: 8px;
                padding: 6px;
                selection-background-color: #000000;
                selection-color: #ffffff;
            }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected {
                background-color: #000000;
                color: #ffffff;
            }
            QMenuBar, QMenu, QToolBar, QStatusBar {
                background-color: #ffffff;
                color: #000000;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background-color: #eeeeee;
                color: #000000;
            }
            QToolBar { border: none; spacing: 6px; padding: 4px; }
            QProgressBar {
                background-color: #f2f2f2;
                color: #000000;
                border: 1px solid #c6c6c6;
                border-radius: 8px;
                text-align: center;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #000000;
                border-radius: 7px;
            }
            QTabWidget::pane { border: 1px solid #d5d5d5; border-radius: 8px; }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #d5d5d5;
                padding: 7px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: 700; }
            QLabel#mutedLabel { color: #666666; }
            QLabel#sectionCaption {
                color: #6b6b6b;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 2px;
            }
            QLabel#hintLabel { color: #8a8a8a; font-size: 11px; }
            QLabel#dialogTitle { font-size: 15px; font-weight: 700; }
            QFrame#translationCard {
                background-color: #ffffff;
                border: 3px solid #000000;
                border-radius: 18px;
            }
            QLabel#phraseDisplay { color: #000000; }
            QFrame#signCard {
                background-color: #fafafa;
                border: 2px solid #bdbdbd;
                border-radius: 14px;
            }
            QLabel#signImage {
                background-color: #ffffff;
                border: 1px dashed #bdbdbd;
                border-radius: 10px;
                color: #333333;
            }
            QLabel#signWord { color: #000000; font-size: 26px; font-weight: 800; }
            QLabel#signDesc { color: #333333; font-size: 15px; }
            QLabel#signMeta { color: #6b6b6b; font-size: 12px; }
        """)

    def show_about(self):
        QMessageBox.about(
            self, "Acerca de",
            "Traductor Voz a Lengua de Señas Chiapaneca - LSM\n\n"
            "Versión 1.1.0\n\n"
            "Aplicación para traducir voz a Lengua de Señas\n"
            "con soporte para variantes regionales de Chiapas\n"
            "y deletreo dactilológico automático.\n\n"
            f"Diccionario: {len(self.dictionary)} palabras\n"
            "1,320 con variante Chiapas | 34,965 Nacional LSM\n\n"
            "Diseñada para proyectarse en el salón de clases.\n\n"
            "Desarrollado para CECYT"
        )


def main():
    # Asegurar un FLAC nativo antes de usar el reconocimiento de voz
    _ensure_flac_in_path()
    app = QApplication(sys.argv)
    app.setApplicationName("Traductor LSC-LSM")

    # Letra base legible en pantallas pequeñas y en proyector.
    base_font = app.font()
    base_font.setPointSize(13)
    app.setFont(base_font)

    window = SignLanguageTranslator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
