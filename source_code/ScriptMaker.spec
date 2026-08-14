# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hidden_imports = [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'requests',
    'dotenv',
    'trafilatura',
    'bs4',
    'yt_dlp',
    'ddgs',
    'tavily',
    'pipeline',
    'research',
    'models',
    'llm',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'h11',
]

def safe_collect_submodules(mod_name):
    try:
        return collect_submodules(mod_name)
    except Exception:
        return [mod_name]

hidden_imports += safe_collect_submodules('trafilatura')
hidden_imports += safe_collect_submodules('yt_dlp')

datas = []
try:
    datas += collect_data_files('trafilatura')
except Exception:
    pass

try:
    datas += collect_data_files('yt_dlp')
except Exception:
    pass

try:
    datas += collect_data_files('certifi')
except Exception:
    pass

for icon_file in ['icon.png', 'icon.ico']:
    if os.path.exists(icon_file):
        datas.append((icon_file, '.'))

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['trio'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ScriptMaker',
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ScriptMaker',
)
