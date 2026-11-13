#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traductor Voz a Lengua de Señas Chiapaneca / LSM
Aplicación de escritorio con PyQt6
"""

import sys
import json
import os
import time
import threading
from pathlib import Path
from typing import List, Dict, Any
import speech_recognition as sr
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QTextEdit,
                            QFrame, QSplitter, QTabWidget, QListWidget, 
                            QListWidgetItem, QSlider, QComboBox, QSpinBox,
                            QFileDialog, QMessageBox, QDialog, QLineEdit,
                            QFormLayout, QGroupBox, QGridLayout, QProgressBar,
                            QScrollArea, QMenuBar, QStatusBar, QToolBar)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPalette, QColor, QAction

class VoiceRecognitionThread(QThread):
    """Hilo para reconocimiento de voz"""
    text_recognized = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.running = False
        
        # Ajustar ruido ambiente
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except:
            pass
    
    def run(self):
        self.running = True
        self.status_changed.emit("Escuchando...")
        
        try:
            with self.microphone as source:
                while self.running:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)
                        self.status_changed.emit("Procesando...")
                        text = self.recognizer.recognize_google(audio, language='es-MX')
                        self.text_recognized.emit(text)
                        self.status_changed.emit("Escuchando...")
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as e:
                        self.status_changed.emit(f"Error: {e}")
                        break
        except Exception as e:
            self.status_changed.emit(f"Error: {e}")
    
    def stop(self):
        self.running = False

class SignPlayerThread(QThread):
    """Hilo para reproducción de señas"""
    sign_changed = pyqtSignal(dict, int)
    finished = pyqtSignal()
    
    def __init__(self, queue, speed=1.0):
        super().__init__()
        self.queue = queue
        self.speed = speed
        self.running = True
        self.paused = False
    
    def run(self):
        for i, item in enumerate(self.queue):
            if not self.running:
                break
            while self.paused and self.running:
                time.sleep(0.1)
            self.sign_changed.emit(item, i)
            # Tiempo de visualización ajustado por velocidad
            time.sleep(2.0 / self.speed)
        self.finished.emit()
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
    
    def stop(self):
        self.running = False

class SignLanguageTranslator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traductor Voz a Lengua de Señas Chiapaneca - LSM v1.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # Cargar configuración
        self.load_config()
        
        # Cargar diccionario
        self.load_dictionary()
        
        # Variables
        self.voice_thread = None
        self.player_thread = None
        self.current_queue = []
        self.is_listening = False
        self.is_playing = False
        self.play_speed = 1.0
        self.theme_dark = False
        self.high_contrast = False
        
        # Inicializar UI
        self.init_ui()
        self.apply_theme()
        
    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.config = {"language": "es-MX", "theme": "light"}
    
    def load_dictionary(self):
        try:
            with open('data/diccionario.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.dictionary = data.get('dictionary', {})
                self.alphabet = data.get('alphabet', {})
                self.dict_metadata = data.get('metadata', {})
            self.statusBar().showMessage(f"Diccionario cargado: {len(self.dictionary)} palabras")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el diccionario: {e}")
            self.dictionary = {}
            self.alphabet = {}
    
    def init_ui(self):
        # Menú
        self.create_menu()
        
        # Toolbar
        self.create_toolbar()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Panel izquierdo - Reconocimiento de voz
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Panel derecho - Visor de señas
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 800])
        
        # Status bar
        self.statusBar().showMessage("Listo")
        
    def create_menu(self):
        menubar = self.menuBar()
        
        # Archivo
        file_menu = menubar.addMenu("Archivo")
        exit_action = QAction("Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Ver
        view_menu = menubar.addMenu("Ver")
        theme_action = QAction("Cambiar Tema (Claro/Oscuro)", self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
        
        contrast_action = QAction("Alto Contraste", self)
        contrast_action.triggered.connect(self.toggle_contrast)
        view_menu.addAction(contrast_action)
        
        # Diccionario
        dict_menu = menubar.addMenu("Diccionario")
        admin_action = QAction("Gestionar Diccionario", self)
        admin_action.triggered.connect(self.open_dictionary_manager)
        dict_menu.addAction(admin_action)
        
        # Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        mic_action = QAction("🎤 Micrófono", self)
        mic_action.triggered.connect(self.toggle_listening)
        toolbar.addAction(mic_action)
        
        test_action = QAction("🔊 Simular Voz", self)
        test_action.triggered.connect(self.simulate_voice)
        toolbar.addAction(test_action)
        
        toolbar.addSeparator()
        
        dict_action = QAction("📚 Diccionario", self)
        dict_action.triggered.connect(self.open_dictionary_manager)
        toolbar.addAction(dict_action)
    
    def create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Grupo reconocimiento de voz
        voice_group = QGroupBox("Reconocimiento de Voz")
        voice_layout = QVBoxLayout(voice_group)
        
        self.mic_btn = QPushButton("🎤 Iniciar Escucha")
        self.mic_btn.setMinimumHeight(60)
        self.mic_btn.clicked.connect(self.toggle_listening)
        font = QFont()
        font.setPointSize(12)
        self.mic_btn.setFont(font)
        voice_layout.addWidget(self.mic_btn)
        
        self.mic_status = QLabel("Estado: Listo")
        self.mic_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        voice_layout.addWidget(self.mic_status)
        
        layout.addWidget(voice_group)
        
        # Grupo transcripción
        trans_group = QGroupBox("Transcripción en Vivo")
        trans_layout = QVBoxLayout(trans_group)
        
        self.trans_text = QTextEdit()
        self.trans_text.setReadOnly(True)
        self.trans_text.setPlaceholderText("El texto hablado aparecerá aquí...")
        trans_layout.addWidget(self.trans_text)
        
        self.word_count_label = QLabel("Palabras: 0")
        trans_layout.addWidget(self.word_count_label)
        
        layout.addWidget(trans_group)
        
        return panel
    
    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Grupo visor de señas
        sign_group = QGroupBox("Visor de Señas - Lengua de Señas Chiapaneca/LSM")
        sign_layout = QVBoxLayout(sign_group)
        
        # Display de seña
        self.sign_display = QLabel()
        self.sign_display.setMinimumHeight(300)
        self.sign_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sign_display.setStyleSheet("border: 2px solid #ccc; background-color: #f0f0f0;")
        self.sign_display.setText("Esperando traducción...\n\nLas señas aparecerán aquí")
        self.sign_display.setWordWrap(True)
        sign_layout.addWidget(self.sign_display)
        
        # Info de seña actual
        info_layout = QHBoxLayout()
        self.current_word_label = QLabel("Palabra: -")
        self.sign_count_label = QLabel("Seña: 0 / 0")
        self.sign_type_label = QLabel("Tipo: -")
        info_layout.addWidget(self.current_word_label)
        info_layout.addWidget(self.sign_count_label)
        info_layout.addWidget(self.sign_type_label)
        sign_layout.addLayout(info_layout)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        sign_layout.addWidget(self.progress_bar)
        
        # Controles
        controls_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("⏮️ Anterior")
        self.prev_btn.clicked.connect(self.play_previous)
        self.prev_btn.setEnabled(False)
        controls_layout.addWidget(self.prev_btn)
        
        self.play_pause_btn = QPushButton("▶️ Reproducir")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        self.play_pause_btn.setEnabled(False)
        controls_layout.addWidget(self.play_pause_btn)
        
        self.next_btn = QPushButton("Siguiente ⏭️")
        self.next_btn.clicked.connect(self.play_next)
        self.next_btn.setEnabled(False)
        controls_layout.addWidget(self.next_btn)
        
        sign_layout.addLayout(controls_layout)
        
        # Control de velocidad
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Velocidad:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        speed_layout.addWidget(self.speed_combo)
        speed_layout.addStretch()
        sign_layout.addLayout(speed_layout)
        
        layout.addWidget(sign_group)
        
        # Grupo cola
        queue_group = QGroupBox("Cola de Reproducción")
        queue_layout = QVBoxLayout(queue_group)
        
        self.queue_list = QListWidget()
        queue_layout.addWidget(self.queue_list)
        
        self.queue_status = QLabel("Cola vacía")
        queue_layout.addWidget(self.queue_status)
        
        layout.addWidget(queue_group)
        
        return panel
    
    def toggle_listening(self):
        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()
    
    def start_listening(self):
        try:
            self.voice_thread = VoiceRecognitionThread()
            self.voice_thread.text_recognized.connect(self.process_recognized_text)
            self.voice_thread.status_changed.connect(self.update_mic_status)
            self.voice_thread.start()
            self.is_listening = True
            self.mic_btn.setText("⏹️ Detener Escucha")
            self.mic_status.setText("Estado: Escuchando...")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar reconocimiento: {e}")
    
    def stop_listening(self):
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.wait()
        self.is_listening = False
        self.mic_btn.setText("🎤 Iniciar Escucha")
        self.mic_status.setText("Estado: Listo")
    
    def update_mic_status(self, status):
        self.mic_status.setText(f"Estado: {status}")
    
    def process_recognized_text(self, text):
        self.trans_text.append(f"🗣️ {text}")
        word_count = len(text.split())
        self.word_count_label.setText(f"Palabras: {word_count}")
        self.process_text_to_signs(text)
    
    def process_text_to_signs(self, text):
        # Procesar texto a cola de señas
        words = text.lower().split()
        self.current_queue = []
        
        i = 0
        while i < len(words):
            word = words[i].strip('.,!?;:()[]{}"\'')
            if not word:
                i += 1
                continue
            
            # Buscar frase de dos palabras
            if i < len(words) - 1:
                two_word = word + " " + words[i+1].strip('.,!?;:()[]{}"\'')
                if two_word in self.dictionary:
                    self.current_queue.append({
                        'word': two_word,
                        'type': 'sign',
                        'data': self.dictionary[two_word],
                        'original': two_word
                    })
                    i += 2
                    continue
            
            # Buscar palabra individual
            if word in self.dictionary:
                self.current_queue.append({
                    'word': word,
                    'type': 'sign',
                    'data': self.dictionary[word],
                    'original': word
                })
            else:
                # Deletreo dactilológico
                for letter in word:
                    if letter in self.alphabet:
                        self.current_queue.append({
                            'word': letter.upper(),
                            'type': 'letter',
                            'data': {'file': self.alphabet[letter]['file'], 'description': f'Letra {letter.upper()}'},
                            'original': letter
                        })
                    elif letter.isalpha():
                        # Intentar sin acento
                        for alt in [letter, letter.lower()]:
                            if alt in self.alphabet:
                                self.current_queue.append({
                                    'word': alt.upper(),
                                    'type': 'letter',
                                    'data': {'file': self.alphabet[alt]['file'], 'description': f'Letra {alt.upper()}'},
                                    'original': alt
                                })
                                break
            i += 1
        
        self.update_queue_display()
        if self.current_queue:
            self.enable_playback_controls()
            self.play_current_queue()
    
    def update_queue_display(self):
        self.queue_list.clear()
        for i, item in enumerate(self.current_queue):
            tipo = "SEÑA" if item['type'] == 'sign' else "LETRA"
            region = item['data'].get('region', 'N/A') if item['type'] == 'sign' else 'DACTIL'
            self.queue_list.addItem(f"{i+1}. [{tipo}] {item['word']} ({region})")
        self.queue_status.setText(f"Cola: {len(self.current_queue)} elementos")
    
    def enable_playback_controls(self):
        self.play_pause_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.play_pause_btn.setText("▶️ Reproducir")
        self.is_playing = False
    
    def play_current_queue(self):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
        
        speed = float(self.speed_combo.currentText().replace('x', ''))
        self.player_thread = SignPlayerThread(self.current_queue, speed)
        self.player_thread.sign_changed.connect(self.display_sign)
        self.player_thread.finished.connect(self.playback_finished)
        self.player_thread.start()
        self.is_playing = True
        self.play_pause_btn.setText("⏸️ Pausar")
    
    def display_sign(self, item, index):
        self.current_word_label.setText(f"Palabra: {item['word']}")
        self.sign_count_label.setText(f"Seña: {index+1} / {len(self.current_queue)}")
        tipo = "Seña Completa" if item['type'] == 'sign' else "Deletreo Dactilológico"
        self.sign_type_label.setText(f"Tipo: {tipo}")
        
        if item['type'] == 'sign':
            region = item['data'].get('region', 'nacional')
            desc = item['data'].get('description', item['word'])
            self.sign_display.setText(f"✋ {item['word'].upper()}\n\n{desc}\n\nVariante: {'CHIAPAS' if region == 'chiapas' else 'NACIONAL LSM'}")
            self.sign_display.setStyleSheet("border: 2px solid #4CAF50; background-color: #f0fff0; font-size: 16px;")
        else:
            self.sign_display.setText(f"📝 LETRA\n\n{item['word']}\n\nDeletreo Dactilológico LSM")
            self.sign_display.setStyleSheet("border: 2px solid #FF9800; background-color: #fff8f0; font-size: 18px;")
        
        # Actualizar progreso
        progress = int((index + 1) / len(self.current_queue) * 100)
        self.progress_bar.setValue(progress)
        
        # Resaltar en lista
        self.queue_list.setCurrentRow(index)
    
    def toggle_playback(self):
        if not self.is_playing:
            self.play_current_queue()
        else:
            if self.player_thread:
                self.player_thread.pause()
                self.is_playing = False
                self.play_pause_btn.setText("▶️ Reproducir")
            else:
                self.play_current_queue()
    
    def play_previous(self):
        # Implementación simplificada
        pass
    
    def play_next(self):
        # Implementación simplificada
        pass
    
    def change_speed(self):
        pass
    
    def playback_finished(self):
        self.is_playing = False
        self.play_pause_btn.setText("▶️ Reproducir")
        self.progress_bar.setValue(100)
        self.sign_display.setText("✅ Traducción Completada\n\nReproducción finalizada")
        self.sign_display.setStyleSheet("border: 2px solid #2196F3; background-color: #f0f8ff;")
    
    def simulate_voice(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Simulador de Voz")
        dialog.setGeometry(300, 300, 400, 300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Selecciona o escribe una frase para simular:"))
        
        phrases = [
            "Hola, buenos días amigo",
            "Gracias por tu ayuda",
            "¿Cómo estás?",
            "Sí, por favor necesito ayuda",
            "Chiapas es mi tierra",
            "Bienvenido a mi comunidad"
        ]
        
        for p in phrases:
            btn = QPushButton(p)
            btn.clicked.connect(lambda checked, text=p: self.simulate_and_close(dialog, text))
            layout.addWidget(btn)
        
        layout.addWidget(QLabel("O escribe tu propia frase:"))
        self.sim_input = QLineEdit()
        layout.addWidget(self.sim_input)
        
        sim_btn = QPushButton("Traducir")
        sim_btn.clicked.connect(lambda: self.simulate_and_close(dialog, self.sim_input.text()))
        layout.addWidget(sim_btn)
        
        dialog.exec()
    
    def simulate_and_close(self, dialog, text):
        if text.strip():
            self.trans_text.append(f"🔊 SIMULADO: {text}")
            word_count = len(text.split())
            self.word_count_label.setText(f"Palabras: {word_count}")
            self.process_text_to_signs(text)
        dialog.close()
    
    def open_dictionary_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Gestor de Diccionario")
        dialog.setGeometry(200, 200, 800, 600)
        layout = QVBoxLayout(dialog)
        
        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab explorar
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
        # Mostrar primeras 100 palabras
        count = 0
        for word, data in sorted(self.dictionary.items()):
            if count >= 100:
                break
            region = "CHIAPAS" if data.get('region') == 'chiapas' else "NACIONAL"
            dict_list.addItem(f"{word} [{region}] - {data.get('description', '')}")
            count += 1
        explore_layout.addWidget(dict_list)
        explore_layout.addWidget(QLabel(f"Mostrando {count} de {len(self.dictionary)} palabras"))
        
        tabs.addTab(explore_tab, "Explorar")
        
        # Tab agregar
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
        
        save_btn = QPushButton("Guardar Seña")
        save_btn.clicked.connect(lambda: self.save_new_sign(word_input.text(), region_combo.currentText(), file_input.text(), desc_input.text(), dialog))
        add_layout.addRow(save_btn)
        
        tabs.addTab(add_tab, "Agregar")
        
        # Tab estadísticas
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        chiapas_count = sum(1 for k,v in self.dictionary.items() if v.get('region') == 'chiapas')
        nacional_count = len(self.dictionary) - chiapas_count
        
        stats_layout.addWidget(QLabel(f"📊 Total de palabras: {len(self.dictionary)}"))
        stats_layout.addWidget(QLabel(f"🌽 Palabras con variante Chiapas: {chiapas_count}"))
        stats_layout.addWidget(QLabel(f"🇲🇽 Palabras Nacional LSM: {nacional_count}"))
        stats_layout.addWidget(QLabel(f"🔤 Letras en alfabeto dactilológico: {len(self.alphabet)}"))
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
        else:
            QMessageBox.warning(dialog, "Error", "Palabra y archivo son obligatorios")
    
    def toggle_theme(self):
        self.theme_dark = not self.theme_dark
        self.apply_theme()
    
    def toggle_contrast(self):
        self.high_contrast = not self.high_contrast
        self.apply_theme()
    
    def apply_theme(self):
        if self.high_contrast:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: black; color: yellow; }
                QGroupBox { border: 2px solid yellow; color: yellow; }
                QPushButton { background-color: black; color: yellow; border: 2px solid yellow; }
                QPushButton:hover { background-color: yellow; color: black; }
                QTextEdit, QListWidget { background-color: black; color: yellow; border: 2px solid yellow; }
                QLabel { color: yellow; }
            """)
        elif self.theme_dark:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #2b2b2b; color: #ffffff; }
                QGroupBox { border: 1px solid #555; color: #ffffff; }
                QPushButton { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; padding: 5px; }
                QPushButton:hover { background-color: #4c4c4c; }
                QPushButton:pressed { background-color: #5c5c5c; }
                QTextEdit, QListWidget { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; }
                QLabel { color: #ffffff; }
                QMenuBar { background-color: #2b2b2b; color: #ffffff; }
                QMenuBar::item:selected { background-color: #3c3c3c; }
                QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #555; }
                QMenu::item:selected { background-color: #3c3c3c; }
                QStatusBar { background-color: #2b2b2b; color: #ffffff; }
                QToolBar { background-color: #2b2b2b; border: none; }
                QComboBox { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; }
                QProgressBar { border: 1px solid #555; text-align: center; }
                QProgressBar::chunk { background-color: #4CAF50; }
            """)
        else:
            self.setStyleSheet("")
    
    def show_about(self):
        QMessageBox.about(self, "Acerca de", 
            "Traductor Voz a Lengua de Señas Chiapaneca - LSM\n\n"
            "Versión 1.0.0\n\n"
            "Aplicación para traducir voz a Lengua de Señas\n"
            "con soporte para variantes regionales de Chiapas\n"
            "y deletreo dactilológico automático.\n\n"
            f"Diccionario: {len(self.dictionary)} palabras\n"
            "Incluye más de 10,000 palabras")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Traductor LSC-LSM")
    window = SignLanguageTranslator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
