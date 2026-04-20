# -*- mode: python ; coding: utf-8 -*-
# ANTIVYRE — PyInstaller Build Specification
#
# Usage:
#   pip install pyinstaller
#   pyinstaller build.spec
#
# Output: dist/Antivyre/   (folder with .exe + all deps)
# Then run Inno Setup on installer/antivyre.iss to produce Setup.exe

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Include ALL data files the app needs at runtime
        (str(ROOT / 'locales'),  'locales'),
        (str(ROOT / 'assets'),   'assets'),
        (str(ROOT / 'db' / 'malicious_hashes.txt'), 'db'),
        # Magika ships its own model files — locate them from the Python environment
        (str(Path(__import__('magika').__file__).parent / 'models'), 'magika/models'),
        (str(Path(__import__('magika').__file__).parent / 'config'), 'magika/config'),
    ],
    hiddenimports=[
        # Magika / ONNX
        'magika',
        'magika.types',
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',
        # PIL / pystray
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageTk',
        'pystray',
        'pystray._win32',
        # psutil
        'psutil',
        'psutil._pswindows',
        # tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # stdlib
        'sqlite3',
        'json',
        'threading',
        'webbrowser',
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unnecessary large packages
        'matplotlib', 'numpy.distutils', 'scipy',
        'IPython', 'jupyter', 'notebook',
        'PyQt5', 'PyQt6', 'wx',
        'pytest', 'setuptools',
    ],
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
    name='ANTIVYRE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                              # Compress with UPX if available
    console=False,                         # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],              # App icon in taskbar & explorer
    version='version_info.txt',            # Windows version resource (optional)
    app_name='ANTIVYRE',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ANTIVYRE',                  # Output folder: dist/ANTIVYRE/
)
