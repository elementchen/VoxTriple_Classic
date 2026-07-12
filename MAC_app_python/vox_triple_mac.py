#!/usr/bin/env python3
"""VoxTriple — ESP32 BT Microphone Config (macOS)

Shares ble_client.py and config_service.py with the Windows version.
Keyboard I/O is Mac-specific (keyboard_io_mac.py).
Requires Accessibility permission in System Settings for keyboard capture.
"""
import sys, os, asyncio, logging, tkinter as tk
from tkinter import ttk

# Import shared modules from sibling windows_app_python directory
_shared = os.path.join(os.path.dirname(__file__), "..", "windows_app_python")
if os.path.isdir(_shared):
    sys.path.insert(0, os.path.abspath(_shared))

import ble_client
import config_service
import keyboard_io_mac as keyboard_io

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("VoxTriple")


# ── Async helpers ─────────────────────────────────────────────────
_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    if _loop is None:
        return None
    return asyncio.run_coroutine_threadsafe(coro, _loop)


def start_asyncio_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def stop_asyncio_loop():
    if _loop:
        _loop.call_soon_threadsafe(_loop.stop)


# ── Modifier helpers ──────────────────────────────────────────────
_MOD_MASKS = {
    "lc": 0x01, "ls": 0x02, "la": 0x04, "lw": 0x08,
    "rc": 0x10, "rs": 0x20, "ra": 0x40, "rw": 0x80,
}


def _build_modifier(vars: dict) -> int:
    mod = 0
    for key, mask in _MOD_MASKS.items():
        if vars.get(key, tk.BooleanVar()).get():
            mod |= mask
    return mod


# ── Main Application ──────────────────────────────────────────────
class VoxTripleApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VoxTriple — ESP32 BT Mic Config (macOS)")
        self.root.geometry("640x620")
        self.root.minsize(600, 560)

        self.ble = ble_client.BleClient()
        self.ble.on_button_event = self._on_button_event
        self.ble.on_status = self._on_status

        # Config
        self._cfg = config_service.load()

        # Button state
        self._btn = []
        for i in range(4):
            key = f"button{i+1}"
            b = self._cfg.get(key, {"vk_code": 0x0D, "modifier": 0})
            self._btn.append({
                "vk": tk.IntVar(value=b["vk_code"]),
                "mod_vars": {},
                "capturing": False,
                "display": tk.StringVar(value=keyboard_io.build_display(b["vk_code"], b["modifier"])),
            })
            for mk in _MOD_MASKS:
                self._btn[i]["mod_vars"][mk] = tk.BooleanVar(value=bool(b["modifier"] & _MOD_MASKS[mk]))
                self._btn[i]["mod_vars"][mk].trace_add("write", lambda *a, idx=i: self._update_display(idx))

        self._tx_power = self._cfg.get("tx_power", 4)
        self._sleep_mode = tk.BooleanVar(value=self._cfg.get("sleep_mode", True))

        self._status_text = tk.StringVar(value="Searching for device...")
        self._last_event_text = tk.StringVar(value="None")
        self._connected = False

        self._build_ui()

        # Auto-connect on startup if previously paired
        if self._cfg.get("ble_address", 0):
            root.after(500, lambda: _run_async(self._auto_connect()))

    # ── UI construction ───────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 4, "pady": 2}

        # 1. Setup Custom Visual Styling (Revert to clean Native theme with custom card bg)
        style = ttk.Style()
        
        BG_COLOR = "#f4f6f8"       # Soft light gray for general window background
        CARD_COLOR = "#ffffff"     # Clean white for tab pages and card containers
        PRIMARY_COLOR = "#16a085"  # Teal highlight
        TEXT_COLOR = "#2c3e50"
        
        self.root.configure(background=BG_COLOR)
        
        # Base global style overrides
        style.configure(".", background=CARD_COLOR, foreground=TEXT_COLOR, fieldbackground=CARD_COLOR)
        
        # Dedicated Styles for header elements (must match base BG)
        style.configure("Header.TLabelframe", background=BG_COLOR, bordercolor="#d5d8dc")
        style.configure("Header.TLabelframe.Label", background=BG_COLOR, font=("Helvetica", 9, "bold"), foreground=TEXT_COLOR)
        style.configure("Header.TFrame", background=BG_COLOR)
        style.configure("Header.TLabel", background=BG_COLOR, foreground=TEXT_COLOR)
        
        # Tab content structures (white background)
        style.configure("TLabelframe", background=CARD_COLOR, bordercolor="#e6ecef")
        style.configure("TLabelframe.Label", background=CARD_COLOR, font=("Helvetica", 9, "bold"), foreground=PRIMARY_COLOR)
        style.configure("TFrame", background=CARD_COLOR)
        style.configure("TLabel", background=CARD_COLOR, foreground=TEXT_COLOR)
        style.configure("TCheckbutton", background=CARD_COLOR, foreground=TEXT_COLOR)
        
        # Configure Notebook and Tabs using native system frame shapes
        style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
        style.configure("TNotebook.Tab", 
                        font=("Helvetica", 9, "bold"), 
                        padding=[16, 6])
        
        style.map("TNotebook.Tab",
                  foreground=[("selected", PRIMARY_COLOR), ("active", TEXT_COLOR)])

        # --- 常驻顶部控制台: Connection & Monitoring (3 Rows Layout) ---
        top_frame = ttk.LabelFrame(self.root, text="Device Status & Connection / 设备连接与状态监控", padding=10, style="Header.TLabelframe")
        top_frame.pack(fill="x", padx=8, pady=4)

        # Line 1: Connection Controllers
        ctrl_row = ttk.Frame(top_frame, style="Header.TFrame")
        ctrl_row.pack(fill="x", pady=4)
        
        self._pair_btn = ttk.Button(ctrl_row, text="Pair New / 蓝牙配对连接", command=self._scan_connect, takefocus=False)
        self._pair_btn.pack(side="left", padx=4)
        
        self._disconn_btn = ttk.Button(ctrl_row, text="Disconnect / 断开", command=self._disconnect, takefocus=False)
        self._disconn_btn.pack(side="left", padx=4)

        # Line 2: Status tags (HFP state & Audio link)
        status_row = ttk.Frame(top_frame, style="Header.TFrame")
        status_row.pack(fill="x", pady=4)
        
        self._hfp_label = ttk.Label(status_row, text="HFP State: --", font=("Helvetica", 9, "bold"), style="Header.TLabel")
        self._hfp_label.pack(side="left", padx=8)
        
        self._audio_label = ttk.Label(status_row, text="Audio Link: --", font=("Helvetica", 9, "bold"), style="Header.TLabel")
        self._audio_label.pack(side="left", padx=8)

        # Line 3: System Status Prompt & Big Live Key monitoring display
        mon_row = ttk.Frame(top_frame, style="Header.TFrame")
        mon_row.pack(fill="x", pady=(4, 0))
        
        self._status_label = ttk.Label(mon_row, textvariable=self._status_text, foreground="gray", style="Header.TLabel")
        self._status_label.pack(side="left", padx=4)
        
        evt_sub = ttk.Frame(mon_row, style="Header.TFrame")
        evt_sub.pack(side="right", padx=4)
        ttk.Label(evt_sub, text="Last Key Press / 最近按键: ", font=("Helvetica", 9, "bold"), foreground="#7f8c8d", style="Header.TLabel").pack(side="left")
        
        # Highlighted large text for instant feedback
        self._live_evt_label = ttk.Label(evt_sub, textvariable=self._last_event_text, font=("Helvetica", 11, "bold"), foreground="#d35400", style="Header.TLabel")
        self._live_evt_label.pack(side="left", padx=4)

        # --- Notebook Container for Tabs ---
        notebook = ttk.Notebook(self.root, padding=4, takefocus=False)
        notebook.pack(fill="both", expand=True, padx=8, pady=4)

        # ==========================================
        # TAB 1: Keyboard Config (键盘配置热更新)
        # ==========================================
        tab_config = ttk.Frame(notebook, padding=6)
        notebook.add(tab_config, text="Keyboard Config / 按键与配置")

        # 2x2 grid frame for 4 button configs
        buttons_grid_frame = ttk.Frame(tab_config)
        buttons_grid_frame.pack(fill="x", pady=2)
        buttons_grid_frame.columnconfigure(0, weight=1)
        buttons_grid_frame.columnconfigure(1, weight=1)

        self._cap_btns = [None, None, None, None]
        self._build_button_group(buttons_grid_frame, 0, 0, 0)
        self._build_button_group(buttons_grid_frame, 1, 0, 1)
        self._build_button_group(buttons_grid_frame, 2, 1, 0)
        self._build_button_group(buttons_grid_frame, 3, 1, 1)

        # Bottom row for Tab 1: Device general settings (TX power & sleep)
        dev_frame = ttk.LabelFrame(tab_config, text="Device Settings / 设备设置", padding=8)
        dev_frame.pack(fill="x", padx=4, pady=6)
        
        dev_row = ttk.Frame(dev_frame)
        dev_row.pack(fill="x")
        ttk.Label(dev_row, text="TX Power / 发射功率:", font=("Helvetica", 9, "bold")).pack(side="left", padx=4)
        self._tx_combo = ttk.Combobox(dev_row, width=18,
                                values=["0: -12 dBm (min)", "1: -9 dBm", "2: -6 dBm",
                                        "3: -3 dBm", "4: 0 dBm", "5: +3 dBm",
                                        "6: +6 dBm", "7: +9 dBm (max)"],
                                state="readonly")
        self._tx_combo.current(self._tx_power)
        self._tx_combo.bind("<<ComboboxSelected>>", self._on_tx_power_change)
        self._tx_combo.pack(side="left", padx=4)
        
        ttk.Label(dev_row, text="Sleep Mode / 睡眠模式:", font=("Helvetica", 9, "bold")).pack(side="left", padx=(16, 4))
        ttk.Checkbutton(dev_row, text="Enabled / 启用", variable=self._sleep_mode, takefocus=False).pack(side="left")

        # Action buttons
        act_frame = ttk.Frame(tab_config)
        act_frame.pack(pady=(6, 0))
        ttk.Button(act_frame, text="Write to Device / 写入到设备", command=self._write_device, takefocus=False).pack(side="left", **pad)
        ttk.Button(act_frame, text="Save Config / 存入配置文件", command=self._save_file, takefocus=False).pack(side="left", **pad)
        ttk.Button(act_frame, text="Load Config / 读取配置文件", command=self._load_file, takefocus=False).pack(side="left", **pad)

        # ==========================================
        # TAB 2: Info & Guide (使用说明)
        # ==========================================
        tab_info = ttk.Frame(notebook, padding=6)
        notebook.add(tab_info, text="Info / 使用说明")

        info_frame = ttk.LabelFrame(tab_info, text="Instruction Guide / 操作指南", padding=12)
        info_frame.pack(fill="both", expand=True, padx=4, pady=4)
        msg = ("• Click 'Capture' then press a physical key on your Mac keyboard to assign it.\n"
               "• Modifiers (Ctrl, Shift, Option, Cmd) are combined and sent when you click 'Write to Device'.\n"
               "• Configurations take effect immediately without reboot.\n"
               "• The keyboard stores mappings locally and works standalone without this App.\n\n"
               "• Keyboard capture requires Accessibility permission under macOS:\n"
               "  System Settings → Privacy & Security → Accessibility\n\n"
               "• 点击「Capture / 捕获」然后按下您电脑键盘上的实体按键来捕获。\n"
               "• 勾选修饰键（Ctrl, Shift, Option, Cmd）后，点击「写入到设备」进行热更新。\n"
               "• 键盘设备独立保存配置，日常工作无需开启此配置 App。\n\n"
               "• 注意：Mac 端的键盘按键捕获需要您的系统提供辅助功能权限：\n"
               "  系统设置 → 隐私与安全性 → 辅助功能，请将此应用添加并勾选允许。")
        ttk.Label(info_frame, text=msg, foreground="#555555", font=("Helvetica", 9), justify="left").pack(anchor="nw", fill="both", expand=True)

        # Quit cleanup
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_button_group(self, parent_frame, i: int, row: int, col: int):
        b = self._btn[i]
        group = ttk.LabelFrame(parent_frame, text=f"Button {i+1}", padding=6)
        group.grid(row=row, column=col, padx=6, pady=4, sticky="nsew")

        key_row = ttk.Frame(group)
        key_row.pack(fill="x", pady=2)
        ttk.Label(key_row, text="Key:", width=5, font=("Helvetica", 9, "bold")).pack(side="left")
        ttk.Label(key_row, textvariable=b["display"], width=13, relief="sunken", background="#f0f0f0").pack(side="left", padx=4)
        
        btn = ttk.Button(key_row, text="Capture / 捕获", command=lambda idx=i: self._begin_capture(idx), takefocus=False)
        btn.pack(side="left", padx=4)
        self._cap_btns[i] = btn

        mod_frame = ttk.Frame(group)
        mod_frame.pack(fill="x", pady=2)
        
        mod_row1 = ttk.Frame(mod_frame)
        mod_row1.pack(fill="x")
        for mk in ["lc", "ls", "la", "lw"]:
            label = {"lc": "Ctrl", "ls": "Shift", "la": "Option", "lw": "Cmd"}[mk]
            ttk.Checkbutton(mod_row1, text=label, variable=b["mod_vars"][mk], takefocus=False).pack(side="left", padx=2)
            
        mod_row2 = ttk.Frame(mod_frame)
        mod_row2.pack(fill="x", pady=(2, 0))
        for mk in ["rc", "rs", "ra", "rw"]:
            label = {"rc": "RCtrl", "rs": "RShift", "ra": "ROption", "rw": "RCmd"}[mk]
            ttk.Checkbutton(mod_row2, text=label, variable=b["mod_vars"][mk], takefocus=False).pack(side="left", padx=2)

    # ── Display update ────────────────────────────────────────────
    def _update_display(self, idx: int):
        b = self._btn[idx]
        mod = _build_modifier(b["mod_vars"])
        b["display"].set(keyboard_io.build_display(b["vk"].get(), mod))

    # ── Key capture ───────────────────────────────────────────────
    def _begin_capture(self, idx: int):
        for i, b in enumerate(self._btn):
            b["capturing"] = (i == idx)
        self._cap_btns[idx].configure(text="Capturing... / 捕获中...")
        self._status_text.set(f"Capturing key for Button {idx+1}… Press a key.")

        def on_key(vk: int, _ext, _sc):
            if 0 <= idx < 4:
                self._btn[idx]["vk"].set(vk)
                self._update_display(idx)
            self._status_text.set("Key captured.")
            self._cap_btns[idx].configure(text="Capture / 捕获")
            keyboard_io.stop_key_capture()

        keyboard_io.start_key_capture(on_key, self.root)

    def _on_tx_power_change(self, event):
        self._tx_power = self._tx_combo.current()
        if self._tx_power < 0:
            self._tx_power = 4

    # ── BLE operations ────────────────────────────────────────────
    def _scan_connect(self):
        _run_async(self._do_scan_connect())

    async def _do_scan_connect(self):
        self._status_text.set("Scanning...")
        addr = await ble_client.BleClient.scan()
        if not addr:
            self._status_text.set("ESP32_BT_MIC not found.")
            return
        self._status_text.set("Connecting...")
        ok = await self.ble.connect(addr)
        if ok:
            self._connected = True
            self._cfg["ble_address"] = int(addr.replace(":", ""), 16)
            self._cfg["device_address"] = addr
            config_service.save(self._cfg)
            self._status_text.set(f"Connected: {addr}")
            for i in range(4):
                r = await self.ble.read_button_mapping(i)
                if r:
                    self._btn[i]["vk"].set(r[0])
                    for mk, mask in _MOD_MASKS.items():
                        self._btn[i]["mod_vars"][mk].set(bool(r[1] & mask))
                    self._update_display(i)
            tx = await self.ble.read_tx_power()
            if tx is not None:
                self._tx_power = tx
                self._tx_combo.current(tx)
            sl = await self.ble.read_sleep_mode()
            if sl is not None:
                self._sleep_mode.set(bool(sl))
        else:
            self._status_text.set("Connection failed.")

    async def _auto_connect(self):
        addr = await ble_client.BleClient.scan(5.0)
        if addr:
            ok = await self.ble.connect(addr)
            if ok:
                self._connected = True
                self._status_text.set(f"Connected: {addr}")
                for i in range(4):
                    r = await self.ble.read_button_mapping(i)
                    if r:
                        self._btn[i]["vk"].set(r[0])
                        for mk, mask in _MOD_MASKS.items():
                            self._btn[i]["mod_vars"][mk].set(bool(r[1] & mask))
                        self._update_display(i)
                tx = await self.ble.read_tx_power()
                if tx is not None:
                    self._tx_power = tx
                    self._tx_combo.current(tx)
                sl = await self.ble.read_sleep_mode()
                if sl is not None:
                    self._sleep_mode.set(bool(sl))
                return
        self._status_text.set("Device not found. Click 'Pair New' or check power.")

    def _disconnect(self):
        _run_async(self.ble.disconnect())
        self._connected = False
        self._status_text.set("Disconnected.")

    def _write_device(self):
        if not self._connected:
            self._status_text.set("BLE not connected.")
            return
        _run_async(self._do_write_device())

    async def _do_write_device(self):
        for i in range(4):
            vk = self._btn[i]["vk"].get()
            mod = _build_modifier(self._btn[i]["mod_vars"])
            ok = await self.ble.write_button_mapping(i, vk, mod)
            if not ok:
                self._status_text.set(f"Write btn{i+1} failed.")
                return
        ok_tx = await self.ble.write_tx_power(self._tx_power)
        if not ok_tx:
            self._status_text.set("Write TX power failed.")
            return
        ok_sl = await self.ble.write_sleep_mode(1 if self._sleep_mode.get() else 0)
        if not ok_sl:
            self._status_text.set("Write sleep mode failed.")
            return
        self._status_text.set("Settings written to device.")
        addr = self.ble.address
        prev = f"Connected: {addr}" if addr else "Ready."
        self.root.after(3000, lambda p=prev: self._status_text.set(p))

    def _save_file(self):
        for i in range(4):
            key = f"button{i+1}"
            self._cfg[key] = {
                "vk_code": self._btn[i]["vk"].get(),
                "modifier": _build_modifier(self._btn[i]["mod_vars"]),
            }
        self._cfg["tx_power"] = self._tx_power
        self._cfg["sleep_mode"] = self._sleep_mode.get()
        config_service.save(self._cfg)
        self._status_text.set("Configuration saved to file.")

    def _save_file(self):
        for i in range(4):
            key = f"button{i+1}"
            self._cfg[key] = {
                "vk_code": self._btn[i]["vk"].get(),
                "modifier": _build_modifier(self._btn[i]["mod_vars"]),
            }
        self._cfg["tx_power"] = self._tx_power
        self._cfg["sleep_mode"] = self._sleep_mode.get()
        config_service.save(self._cfg)
        self._status_text.set("Configuration saved to file.")

    def _load_file(self):
        self._cfg = config_service.load()
        for i in range(4):
            key = f"button{i+1}"
            b = self._cfg.get(key, {"vk_code": 0x0D, "modifier": 0})
            self._btn[i]["vk"].set(b["vk_code"])
            for mk, mask in _MOD_MASKS.items():
                self._btn[i]["mod_vars"][mk].set(bool(b["modifier"] & mask))
            self._update_display(i)
        self._tx_power = self._cfg.get("tx_power", 4)
        self._tx_combo.current(self._tx_power)
        self._sleep_mode.set(self._cfg.get("sleep_mode", True))
        self._status_text.set("Configuration loaded from file.")

    # ── Button event (from BLE) ───────────────────────────────────
    def _on_button_event(self, btn_id: int, state: int):
        self.root.after(0, lambda: self._handle_button_event(btn_id, state))

    def _handle_button_event(self, btn_id: int, state: int):
        s = "PRESSED" if state == 1 else "RELEASED"
        self._last_event_text.set(f"Button {btn_id + 1} {s}")
        # Key input is handled by ESP32 BLE HID directly — no Python simulation needed.

    def _on_status(self, hfp: int, audio: int):
        self.root.after(0, lambda: self._handle_status(hfp, audio))

    def _handle_status(self, hfp: int, audio: int):
        hfp_s = "Connected" if hfp else "--"
        audio_s = "Active" if audio else "--"
        self._hfp_label.configure(text=f"HFP: {hfp_s}")
        self._audio_label.configure(text=f"Audio: {audio_s}")

    def _on_close(self):
        keyboard_io.stop_key_capture()
        _run_async(self.ble.disconnect())
        stop_asyncio_loop()
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────
def main():
    root = tk.Tk()
    VoxTripleApp(root)

    # Start asyncio loop in a background thread
    import threading
    t = threading.Thread(target=start_asyncio_loop, daemon=True)
    t.start()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        stop_asyncio_loop()


if __name__ == "__main__":
    main()
