# -*- mode: python ; coding: utf-8 -*-
from shutil import which


block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[(which("ffmpeg"), "."), (which("ffprobe"), ".")],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='yt_dlp_gui',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt_dlp_gui',
)

app = BUNDLE(coll,
             name='yt_dlp_gui.app',
             bundle_identifier='io.Xpl0itU.yt_dlp_gui')