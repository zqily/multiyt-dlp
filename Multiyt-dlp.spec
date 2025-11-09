# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for the Multiyt-dlp application.

This file is configured for a one-file, windowed (no console) executable
build, including the necessary data files and hidden imports for robust
operation.

Author: zqil
"""

# Block 1: Analysis - Discovering the application's dependencies.
# This is the most critical stage where we define source files, data files,
# and handle modules that PyInstaller might miss.
a = Analysis(
    ['main.py'],  # The main entry point of the application.
    pathex=[],    # No longer needed if running from the project root where main.py resides.
    binaries=[],   # No external binaries are bundled; yt-dlp/ffmpeg are downloaded at runtime.
    datas=[
        ('icon.ico', '.')  # Bundles 'icon.ico' into a 'resources' folder inside the app.
    ],
    hiddenimports=[
        # PRECAUTION: The 'packaging' library is used for version checks and is
        # often missed by PyInstaller's static analysis.
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',

        # PRECAUTION: Pydantic is a complex library that uses dynamic imports.
        # Explicitly including these core modules prevents runtime 'ModuleNotFoundError'.
        'pydantic.v1',
        'pydantic.main',
        'pydantic.networks',
        'pydantic.types',

        # ADDED FOR ROBUSTNESS: aiohttp and its dependencies are often missed.
        # This prevents runtime errors when making network requests for updates or downloads.
        'aiohttp',
        'aiohttp.frozenlist',
        'aiohttp.client_exceptions',
        'aiohttp_charset_normalizer',
        'async_timeout',
        'multidict',
        'yarl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Block 2: PYZ - Creating the Python library archive.
# This bundles all the Python modules found during the Analysis stage into a
# single compressed archive inside the final executable.
pyz = PYZ(a.pure)

# Block 3: EXE - Assembling the final executable.
# This section defines the properties of the final .exe file.
exe = EXE(
    pyz,
    a.scripts,
    [], # Binaries are not collected from Analysis
    [], # Datas are not collected from Analysis
    a.binaries,
    a.datas,
    name='Multiyt-dlp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Set to True to potentially reduce file size, but may affect debugging.
    upx=True,     # Use UPX to compress the final executable if available.
    upx_exclude=[],
    runtime_tmpdir=None,

    # CRITICAL: This is essential for GUI apps on Windows to hide the black console window.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

    # This sets the application icon for the .exe file itself in the file explorer.
    icon='icon.ico',
)