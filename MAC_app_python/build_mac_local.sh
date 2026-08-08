#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=== 1. Creating Virtual Environment ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "=== 2. Installing Dependencies ==="
pip install --upgrade pip
pip install -r ../windows_app_python/requirements.txt
pip install -r requirements.txt

echo "=== 3. Packaging VoxTriple.app via PyInstaller Spec ==="
pyinstaller --clean -y VoxTriple_mac.spec

echo "=== 4. Packaging VoxTriple_mac_cli ==="
pyinstaller --clean -y --onefile --noconsole --name=VoxTriple_mac_cli -p ../windows_app_python vox_triple_mac.py

echo "=== 5. Creating Release Zip Archives ==="
VER="1.0.10"
if [ -f "../esp32_bt_mic/CMakeLists.txt" ]; then
    FOUND_VER=$(grep "set(PROJECT_VER" ../esp32_bt_mic/CMakeLists.txt | cut -d'"' -f2 || true)
    if [ -n "$FOUND_VER" ]; then
        VER="$FOUND_VER"
    fi
fi

cd dist
rm -f VoxTriple_mac_v${VER}.zip VoxTriple_mac_cli_v${VER}.zip
zip -r VoxTriple_mac_v${VER}.zip VoxTriple.app
zip -j VoxTriple_mac_cli_v${VER}.zip VoxTriple_mac_cli

echo "=== macOS Build Completed Successfully! ==="
echo "Artifacts generated in: $SCRIPT_DIR/dist/"
ls -la VoxTriple_mac_v${VER}.zip VoxTriple_mac_cli_v${VER}.zip
