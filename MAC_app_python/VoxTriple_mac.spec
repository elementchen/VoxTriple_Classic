# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Add shared modules path so PyInstaller can find them
_shared = os.path.join(SPECPATH, '..', 'windows_app_python')
if os.path.isdir(_shared):
    sys.path.insert(0, os.path.abspath(_shared))

# ----------------------------------------------------------------
# PyObjC .so files don't match PyInstaller's lib*.so pattern.
# Walk site-packages and collect them manually.
# ----------------------------------------------------------------
_SITE = os.path.join(sys.prefix, 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
_PYOBJC_PKGS = ('Quartz', 'AppKit', 'CoreFoundation', 'CoreBluetooth',
                'Foundation', 'CoreText', 'objc')
_bins = []
for _pkg in _PYOBJC_PKGS:
    _pkg_path = os.path.join(_SITE, _pkg.replace('.', os.sep))
    if os.path.isdir(_pkg_path):
        for _so in Path(_pkg_path).rglob('*.so'):
            _dest = os.path.relpath(os.path.dirname(str(_so)), _SITE)
            _bins.append((str(_so), _dest))

a = Analysis(
    ['vox_triple_mac.py'],
    pathex=[_shared],
    binaries=_bins,
    datas=[],
    hiddenimports=[
        'spp_client',
        'config_service',
        # bleak
        'bleak',
        'bleak.backends.corebluetooth',
        'bleak.backends.corebluetooth.client',
        'bleak.backends.corebluetooth.scanner',
        'bleak.backends.corebluetooth.utils',
        'bleak.backends.corebluetooth.CentralManagerDelegate',
        'bleak.backends.corebluetooth.PeripheralDelegate',
        # CoreBluetooth + Foundation
        'CoreBluetooth',
        'Foundation',
        # pynput
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._darwin',
        'pynput.keyboard._base',
        'pynput._util',
        'pynput._util.darwin',
        'pynput.mouse',
        'pynput.mouse._darwin',
        # pyobjc — force all sub-packages for lazy loading to work
        'objc',
        'Quartz',
        'Quartz.CoreGraphics',
        'Quartz.CoreVideo',
        'Quartz.ImageIO',
        'Quartz.ImageKit',
        'Quartz.PDFKit',
        'Quartz.QuartzComposer',
        'Quartz.QuartzCore',
        'Quartz.QuartzFilters',
        'Quartz.QuickLookUI',
        'AppKit',
        'CoreFoundation',
        'CoreText',
        # urllib + json
        'urllib.request',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoxTriple',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
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
    upx=False,
    upx_exclude=[],
    name='VoxTriple',
)

app = BUNDLE(
    coll,
    name='VoxTriple.app',
    icon=None,
    bundle_identifier='com.voxtriple.config',
    version='1.7.0',
    info_plist={
        'NSHighResolutionCapable': True,
        'NSBluetoothAlwaysUsageDescription': 'VoxTriple uses Bluetooth to configure your ESP32 BT Microphone.',
        'NSBluetoothPeripheralUsageDescription': 'VoxTriple needs Bluetooth to communicate with ESP32.',
        'NSAccessibilityUsageDescription': 'VoxTriple needs Accessibility permissions to capture physical keyboard shortcuts.',
        'LSBackgroundOnly': False,
    },
)
