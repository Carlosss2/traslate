# -*- mode: python ; coding: utf-8 -*-
"""
Configuración de PyInstaller para generar la versión Windows del traductor.

Se genera una carpeta (--onedir), no un solo .exe, porque:
  * arranca más rápido,
  * Windows Defender suele marcar menos los ejecutables de carpeta,
  * es más fácil reemplazar el diccionario o agregar GIFs de señas.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

# Recursos que deben viajar junto al ejecutable.
datas = [
    ("config.json", "."),
    ("README_PYTHON.md", "."),
    ("LEEME_EJECUTABLE.txt", "."),
    ("data", "data"),  # diccionario, señas y alfabeto
]

# SpeechRecognition incluye los conversores FLAC dentro del paquete.
datas += collect_data_files("speech_recognition")

hiddenimports = [
    "pyaudio",
    "speech_recognition",
]

# El resto de dependencias del requirements son para otros scripts del
# proyecto; main.py no las usa y no conviene inflar el ejecutable.
excludes = [
    "tkinter",
    "numpy",
    "pandas",
    "matplotlib",
    "PIL",
    "gtts",
    "pydub",
    "sqlalchemy",
    "watchdog",
    "pytest",
    "tests",
]

icon = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Traductor_LSM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Traductor_LSM",
)
