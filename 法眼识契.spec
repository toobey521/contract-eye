# -*- mode: python ; coding: utf-8 -*-
# 法眼识契 v2.0 — 便携版（含内置 Tesseract OCR）

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('tesseract', 'tesseract'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'pytesseract',
        'PIL',
        'PIL.Image',
        'pydantic',
        'pydantic_core',
        'fastapi',
        'starlette',
        'anyio',
        'sniffio',
        'httptools',
        'wsproto',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'cryptography', 'pandas', 'numpy', 'matplotlib', 'scipy',
        'pywebview', 'webview', 'clr', 'clr_loader', 'pythonnet',
        'PyQt5', 'PySide2', 'PySide6', 'PyQt6',
        'tkinter', 'gi',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='法眼识契',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.py',
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='法眼识契',
)
