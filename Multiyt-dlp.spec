# -*- mode: python ; coding: utf-8 -*-

# This block is for collecting the data files and Python source files.
a = Analysis(
    ['main.py'],  # CORRECT: The entry point of your application is main.py
    pathex=['src'],  # IMPORTANT: Tells PyInstaller to look for imports in the 'src' directory.
    binaries=[],
    datas=[('icon.ico', '.')],  # CORRECT: Bundles icon.ico into the app's root directory.
    hiddenimports=[
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements'
    ],  # PRECAUTION: The 'packaging' library is often missed by PyInstaller's analysis.
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# This creates the .pyz archive containing all the Python modules.
pyz = PYZ(a.pure)

# This defines the final executable file.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Multiyt-dlp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # This is critical for GUI apps on Windows to hide the black console window.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # This sets the application icon for the .exe file itself.
    icon='icon.ico',
)