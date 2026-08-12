#!/usr/bin/env python3
from __future__ import annotations
"""VoxTriple — ESP32 BT Microphone Config (macOS - Webview Edition)

Shares spp_client.py with the Windows version.
Punctuation and keystrokes are captured natively in Webview via JS to avoid system crashes.
Wired config and OTA firmware flashing are handled via physical USB Serial.
"""
import sys
import os
import asyncio
import logging
import urllib.request
import json
import threading
import webview
import serial.tools.list_ports

# Import shared modules from sibling windows_app_python directory
_shared = os.path.join(os.path.dirname(__file__), "..", "windows_app_python")
if os.path.isdir(_shared):
    sys.path.insert(0, os.path.abspath(_shared))

import spp_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("VoxTriple")

# ── Async background loop ──────────────────────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None

def start_asyncio_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_forever()

def run_coro(coro):
    if _loop is None:
        return None
    return asyncio.run_coroutine_threadsafe(coro, _loop)

# ── Webview Python JS-Bridge API ───────────────────────────────────────
class Api:
    def __init__(self):
        self.spp = spp_client.SppClient()
        self.spp.on_button_event = self._on_button_event
        self.spp.on_status = self._on_status
        self._connected = False
        self._window = None
        self._github_version = None
        self._github_bin_url = None

    def set_window(self, window):
        self._window = window

    def get_ports(self) -> list[str]:
        """Scan Mac local for USB Serial ports, filter out virtual bluetooth ports."""
        ports = []
        for p in serial.tools.list_ports.comports():
            if "Bluetooth" not in p.device:
                ports.append(p.device)
        return ports

    def connect_device(self, port: str) -> bool:
        """Connect to physical USB-serial device."""
        log.info(f"Connecting to {port}...")
        future = run_coro(self.spp.connect(port))
        ok = future.result(timeout=6.0)
        self._connected = ok
        return ok

    def disconnect_device(self) -> bool:
        """Disconnect current device."""
        log.info("Disconnecting serial port...")
        future = run_coro(self.spp.disconnect())
        future.result(timeout=3.0)
        self._connected = False
        return True

    def fetch_config(self) -> dict | None:
        """Fetch config cache from the device."""
        if not self._connected:
            return None
            
        future = run_coro(self.spp._fetch_config())
        ok = future.result(timeout=3.0)
        if not ok:
            return None
            
        # Format mapping list to JSON compatible
        config = {
            "version": self.spp._config_cache.get("version", "1.0.9"),
            "tx_power": self.spp._config_cache.get("tx_power", 4),
            "sleep_mode": self.spp._config_cache.get("sleep_mode", 1),
            "mic_enabled": self.spp._config_cache.get("mic_enabled", 1),
            "mappings": []
        }
        for i in range(4):
            vk = self.spp._config_cache.get(f"btn{i+1}_vk", 0)
            mod = self.spp._config_cache.get(f"btn{i+1}_mod", 0)
            config["mappings"].append({"vk": vk, "mod": mod})
            
        return config

    def write_config(self, mappings: list, tx: int, sleep: int, mic: int) -> bool:
        """Write all parameters to board Flash at once."""
        if not self._connected:
            return False
            
        log.info(f"Save parameters: mapping={mappings}, tx={tx}, sleep={sleep}, mic={mic}")
        future = run_coro(self.spp.set_config(mappings, tx, sleep, mic))
        ok = future.result(timeout=5.0)
        return ok

    def select_local_bin(self) -> str | None:
        """Select a local firmware file using macOS native OPEN file dialog."""
        if not self._window:
            return None
        file_types = ('Firmware Files (*.bin)', '*.bin')
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if res and len(res) > 0:
            return res[0]
        return None

    def trigger_ota(self, bin_path: str) -> bool:
        """Upload firmware to ESP32 via serial link."""
        if not self._connected:
            return False
            
        log.info(f"Starting OTA update with file: {bin_path}")
        
        def progress_cb(written, total):
            # Safe dispatch back to Webview container thread
            if self._window:
                self._window.evaluate_js(f"onOtaProgress({written}, {total})")

        future = run_coro(self.spp.upload_firmware(bin_path, progress_cb))
        ok = future.result(timeout=60.0)
        return ok

    def check_update(self):
        """Check GitHub latest update version and prompt user."""
        future = run_coro(self._check_github_version())
        future.result(timeout=5.0)
        
        if self._github_version:
            msg = f"Latest version online: v{self._github_version}\n"
            if self._connected:
                curr = self.spp._config_cache.get("version", "1.0.9")
                msg += f"Your board version: v{curr}\n\n"
                if self._github_version > curr:
                    msg += "New version available! You can select or drag the bin file to update.\n发现新固件版本！你可以拖入或选择固件进行升级。"
                else:
                    msg += "Your device is up to date!\n当前设备固件已是最新版！"
            else:
                msg += "\nPlease connect to device over serial first to compare versions.\n请先连接串口，以便对比版本。"
                
            if self._window:
                self._window.show_dialog("Version Check", msg)
        else:
            if self._window:
                self._window.show_dialog("Error", "Failed to fetch updates from GitHub.\n获取 GitHub 在线更新版本失败，请检查网络！")

    # ── Callbacks ─────────────────────────────────────────────────────────
    def _on_button_event(self, btn_id: int, state: int):
        log.debug(f"Button trigger: {btn_id} state={state}")

    def _on_status(self, hfp: int, audio: int):
        log.debug(f"HFP={hfp} Audio={audio}")

    async def _check_github_version(self):
        url = "https://api.github.com/repos/elementchen/VoxTriple_Classic/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tag = data.get("tag_name", "v1.0.13").strip()
                if tag.startswith("v"):
                    tag = tag[1:]
                self._github_version = tag
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith(".bin") and "merged" not in name:
                        self._github_bin_url = asset.get("browser_download_url")
                        break
        except Exception as e:
            log.warning(f"Check version failed: {e}")

# ── Main Entry ────────────────────────────────────────────────────────────
def main():
    # Start asyncio background loop thread
    global _thread
    _thread = threading.Thread(target=start_asyncio_loop, daemon=True)
    _thread.start()

    # Determine index html assets directory (development vs compiled bundle)
    if hasattr(sys, "_MEIPASS"):
        index_path = os.path.join(sys._MEIPASS, "web", "index.html")
    else:
        index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

    api = Api()
    
    # Enable window stretching and provide proper content padding
    window = webview.create_window(
        title="VoxTriple Config Client macOS", 
        url=index_path, 
        js_api=api,
        width=860,
        height=760,
        min_size=(830, 730),
        resizable=True
    )
    api.set_window(window)

    log.info("Starting PyWebView window...")
    webview.start(debug=False)

if __name__ == '__main__':
    main()
