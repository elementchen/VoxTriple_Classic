#!/usr/bin/env python3
"""VoxTriple — ESP32 BT Microphone Config (macOS)

Shares spp_client.py, config_service.py with the Windows version.
Keyboard I/O is Mac-specific (keyboard_io_mac.py).
Wired config and OTA firmware flashing are handled via physical USB Serial.
Requires Accessibility permission in System Settings for keyboard capture.
"""
import sys, os, asyncio, logging, tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Import shared modules from sibling windows_app_python directory
_shared = os.path.join(os.path.dirname(__file__), "..", "windows_app_python")
if os.path.isdir(_shared):
    sys.path.insert(0, os.path.abspath(_shared))

import spp_client
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
        self.root.geometry("640x700")
        self.root.minsize(600, 640)

        # Connect via SPP Client (re-uses physical USB Serial /dev/cu.* under macOS)
        self.spp = spp_client.SppClient()
        self.spp.on_button_event = self._on_button_event
        self.spp.on_status = self._on_status

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
        self._sleep_mode = tk.BooleanVar(value=True)
        self._mic_enabled = tk.BooleanVar(value=self._cfg.get("mic_enabled", True))

        self._status_text = tk.StringVar(value="Disconnected / 未连接")
        self._last_event_text = tk.StringVar(value="None")
        self._connected = False

        # Cloud update parameters
        self._github_version = None
        self._github_bin_url = None
        self._board_version = None

        self._build_ui()

        # Fill serial ports list on load
        self.root.after(100, self._refresh_ports)

        # Check GitHub version on startup
        root.after(800, lambda: _run_async(self._check_github_version()))

    # ── UI construction ───────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 4, "pady": 2}

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
        style.configure("TNotebook.Tab", font=("Helvetica", 9, "bold"), padding=[16, 6])
        style.map("TNotebook.Tab", foreground=[("selected", PRIMARY_COLOR), ("active", TEXT_COLOR)])

        # --- 常驻顶部控制台: Connection & Monitoring (3 Rows Layout) ---
        top_frame = ttk.LabelFrame(self.root, text="USB Serial Connection & Status / 串口连接与状态监控", padding=10, style="Header.TLabelframe")
        top_frame.pack(fill="x", padx=8, pady=4)

        # Line 1: Connection Controllers
        ctrl_row = ttk.Frame(top_frame, style="Header.TFrame")
        ctrl_row.pack(fill="x", pady=4)
        
        ttk.Label(ctrl_row, text="Serial Port / 串口:", font=("Helvetica", 9, "bold"), style="Header.TLabel").pack(side="left", padx=4)
        self._port_combo = ttk.Combobox(ctrl_row, width=24, state="readonly")
        self._port_combo.pack(side="left", padx=4)
        
        self._conn_btn = ttk.Button(ctrl_row, text="Connect / 连接", command=self._toggle_connect, takefocus=False)
        self._conn_btn.pack(side="left", padx=4)
        
        ttk.Button(ctrl_row, text="Refresh / 刷新", command=self._refresh_ports, takefocus=False).pack(side="left", padx=4)

        # Line 2: Status tags (HFP state & Audio link)
        status_row = ttk.Frame(top_frame, style="Header.TFrame")
        status_row.pack(fill="x", pady=4)
        
        self._hfp_label = ttk.Label(status_row, text="HFP State: --", font=("Helvetica", 9, "bold"), style="Header.TLabel")
        self._hfp_label.pack(side="left", padx=8)
        
        self._audio_label = ttk.Label(status_row, text="Audio Link: --", font=("Helvetica", 9, "bold"), style="Header.TLabel")
        self._audio_label.pack(side="left", padx=8)
        
        self._version_label = ttk.Label(status_row, text="Firmware Version: --", font=("Helvetica", 9, "bold"), foreground="#2980b9", style="Header.TLabel")
        self._version_label.pack(side="left", padx=8)

        self._new_ver_label = ttk.Label(status_row, text="", font=("Helvetica", 9, "bold"), foreground="#d35400", style="Header.TLabel")
        # Kept for dynamic updates (not packed by default)

        self._update_btn = ttk.Button(status_row, text="Update / 升级固件", command=self._on_update_clicked, takefocus=False)
        # Kept for dynamic updates (not packed by default)

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
        self._notebook = notebook

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
        
        ttk.Label(dev_row, text="Microphone / 麦克风:", font=("Helvetica", 9, "bold")).pack(side="left", padx=(16, 4))
        ttk.Checkbutton(dev_row, text="Enabled / 启用", variable=self._mic_enabled, takefocus=False).pack(side="left")

        # Action Button: Write mappings to physical keyboard
        self._write_btn = ttk.Button(tab_config, text="Write to Keyboard / 写入到蓝牙键盘", command=self._write_device, takefocus=False)
        self._write_btn.pack(pady=(4, 0), ipadx=20, ipady=4)

        # ==========================================
        # TAB 2: Firmware OTA (固件升级冷更新)
        # ==========================================
        tab_ota = ttk.Frame(notebook, padding=6)
        notebook.add(tab_ota, text="Firmware OTA / 固件升级")

        ota_frame = ttk.LabelFrame(tab_ota, text="Firmware OTA Upgrade / 固件 OTA 升级", padding=12)
        ota_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Line 1: Select local File (.bin)
        ota_file_row = ttk.Frame(ota_frame)
        ota_file_row.pack(fill="x", pady=6)
        
        self._ota_select_btn = ttk.Button(ota_file_row, text="Select / 选择 (.bin)", command=self._select_firmware, takefocus=False)
        self._ota_select_btn.pack(side="left", padx=4)
        
        self._ota_path_var = tk.StringVar(value="")
        self._ota_entry = ttk.Entry(ota_file_row, textvariable=self._ota_path_var, state="readonly")
        self._ota_entry.pack(side="left", fill="x", expand=True, padx=4)
        
        # Line 2: Flash Action & Progressbar aligned side-by-side
        ota_flash_row = ttk.Frame(ota_frame)
        ota_flash_row.pack(fill="x", pady=10)
        
        self._ota_flash_btn = ttk.Button(ota_flash_row, text="Flash Firmware / 升级固件", command=self._start_ota, takefocus=False)
        self._ota_flash_btn.pack(side="left", padx=4)
        
        self._ota_progress_var = tk.DoubleVar(value=0.0)
        self._ota_progress = ttk.Progressbar(ota_flash_row, variable=self._ota_progress_var, maximum=100)
        self._ota_progress.pack(side="left", fill="x", expand=True, padx=4)
        
        # Line 3: Status Details (Status on left, target bin version on right)
        self._ota_status_text = tk.StringVar(value="Idle / 空闲")
        self._ota_bin_ver_text = tk.StringVar(value="Selected Bin Version: --")
        
        ota_status_row = ttk.Frame(ota_frame)
        ota_status_row.pack(fill="x", pady=4)
        ttk.Label(ota_status_row, textvariable=self._ota_status_text, foreground="gray").pack(side="left", padx=4)
        ttk.Label(ota_status_row, textvariable=self._ota_bin_ver_text, foreground="#16a085", font=("Helvetica", 9, "bold")).pack(side="right", padx=4)

        # ==========================================
        # TAB 3: Info & Guide (使用说明)
        # ==========================================
        tab_info = ttk.Frame(notebook, padding=6)
        notebook.add(tab_info, text="Info / 使用说明")

        info_frame = ttk.LabelFrame(tab_info, text="Instruction Guide / 操作指南", padding=12)
        info_frame.pack(fill="both", expand=True, padx=4, pady=4)
        msg = ("• Connect your VoxTriple board to your Mac via a USB cable.\n"
               "• Select the serial port (e.g. /dev/cu.usbserial-xxx) and click Connect.\n"
               "• Click 'Capture' then press a physical key on your Mac keyboard to assign it.\n"
               "• Modifiers (Ctrl, Shift, Option, Cmd) are combined and sent when you click 'Write'.\n"
               "• Configuration mappings and device settings are written instantly (Hot Update).\n"
               "• Firmware OTA update transfers in ~20 seconds using optimized hardware console links.\n\n"
               "• Keyboard capture requires Accessibility permission under macOS:\n"
               "  System Settings → Privacy & Security → Accessibility\n\n"
               "• 通过 USB 数据线将 VoxTriple 开发板连接到您的 Mac 电脑。\n"
               "• 选择对应的串口设备（如 /dev/cu.usbserial-xxx）并点击「Connect / 连接」。\n"
               "• 点击「Capture / 捕获」然后按下您电脑键盘上的实体按键来捕获。\n"
               "• 勾选修饰键（Ctrl, Shift, Option, Cmd）后，点击「写入到蓝牙键盘」进行热更新。\n"
               "• 键盘设备独立保存按键配置，日常运行无需开启此配置 App。\n\n"
               "• 注意：Mac 端的键盘按键捕获需要您的系统提供辅助功能权限：\n"
               "  系统设置 → 隐私与安全性 → 辅助功能，请将此应用（终端）添加并勾选允许。")
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

    # ── Serial Port Operations ───────────────────────────────────
    def _refresh_ports(self):
        ports = spp_client.SppClient.list_ports()
        combo_vals = [p["desc"] for p in ports]
        self._port_combo["values"] = combo_vals
        
        last_port = self._cfg.get("device_address")
        default_idx = 0
        
        if last_port:
            for idx, p in enumerate(ports):
                if p["port"] == last_port:
                    default_idx = idx
                    break
                    
        if combo_vals:
            self._port_combo.current(default_idx)
        else:
            self._port_combo.set("")

    def _toggle_connect(self):
        if self._connected:
            self._disconnect()
        else:
            sel = self._port_combo.get()
            if not sel:
                self._status_text.set("No serial port selected.")
                return
            port = sel.split(" ")[0]
            self._status_text.set(f"Connecting to {port}…")
            _run_async(self._do_connect(port))

    async def _do_connect(self, port: str):
        ok = await self.spp.connect(port)
        if ok:
            self._connected = True
            self._cfg["device_address"] = port
            config_service.save(self._cfg)
            self.root.after(0, lambda: self._conn_btn.configure(text="Disconnect / 断开"))
            self.root.after(0, lambda: self._status_text.set(f"Connected: {port}"))
            
            # Fetch device configuration cache
            await self._fetch_device_config()
        else:
            self.root.after(0, lambda: self._status_text.set("Connection failed / 连接失败."))

    def _disconnect(self):
        if self._connected:
            _run_async(self.spp.disconnect())
        self._connected = False
        self._conn_btn.configure(text="Connect / 连接")
        self._status_text.set("Disconnected / 已断开.")
        self._hfp_label.configure(text="HFP State: --")
        self._audio_label.configure(text="Audio Link: --")
        self._version_label.configure(text="Firmware Version: --")
        self._board_version = None
        self._compare_and_update_version_ui()

    async def _fetch_device_config(self):
        self._status_text.set("Reading config from device...")
        cfg = await self.spp.get_config()
        if cfg:
            self.root.after(0, lambda: self._status_text.set("Config fetched successfully."))
            
            # Update UI controls according to device config values
            for i in range(4):
                vk_val = cfg["buttons"][i]["vk"]
                mod_val = cfg["buttons"][i]["mod"]
                self._btn[i]["vk"].set(vk_val)
                for mk, mask in _MOD_MASKS.items():
                    self._btn[i]["mod_vars"][mk].set(bool(mod_val & mask))
                self._update_display(i)
                
            self._tx_power = cfg["tx_power"]
            self._tx_combo.current(self._tx_power)
            self._sleep_mode.set(bool(cfg.get("sleep", 1)))
            self._mic_enabled.set(bool(cfg.get("mic_enabled", 1)))
            
            fw_ver = cfg.get("version", "1.0.0")
            self._version_label.configure(text=f"Firmware Version: {fw_ver}")
            self._board_version = fw_ver
            self._compare_and_update_version_ui()
        else:
            self.root.after(0, lambda: self._status_text.set("Failed to read config from device."))

    def _on_tx_power_change(self, event):
        self._tx_power = self._tx_combo.current()
        if self._tx_power < 0:
            self._tx_power = 4

    def _write_device(self):
        if not self._connected:
            messagebox.showerror("Error / 错误", "Please connect to a serial port first!\n请先连上有线串口！")
            return
        
        self._status_text.set("Writing config to device...")
        # Pack mappings
        mapping = []
        for i in range(4):
            vk = self._btn[i]["vk"].get()
            mod = _build_modifier(self._btn[i]["mod_vars"])
            mapping.append({"vk": vk, "mod": mod})
            
        sleep_val = 1
        mic_val = 1 if self._mic_enabled.get() else 0
        _run_async(self._do_write(mapping, self._tx_power, sleep_val, mic_val))

    async def _do_write(self, mapping, tx, sleep, mic_enabled):
        ok = await self.spp.set_config(mapping, tx, sleep, mic_enabled)
        if ok:
            self.root.after(0, lambda: self._status_text.set("Config written! Keyboard is restarting..."))
            # Auto-save local json copy
            self._save_local_file()
        else:
            self.root.after(0, lambda: self._status_text.set("Write config failed / 写入失败."))

    def _save_local_file(self):
        for i in range(4):
            key = f"button{i+1}"
            self._cfg[key] = {
                "vk_code": self._btn[i]["vk"].get(),
                "modifier": _build_modifier(self._btn[i]["mod_vars"]),
            }
        self._cfg["tx_power"] = self._tx_power
        self._cfg["sleep_mode"] = True
        self._cfg["mic_enabled"] = self._mic_enabled.get()
        config_service.save(self._cfg)

    # ── Firmware OTA Flashing ─────────────────────────────────────
    def _read_bin_version(self, bin_path: str) -> str:
        try:
            with open(bin_path, "rb") as f:
                data = f.read(10240)  # Read first 10KB
            magic = b"\x32\x54\xcd\xab"
            idx = data.find(magic)
            if idx != -1:
                ver_bytes = data[idx + 16 : idx + 16 + 32]
                if b"\x00" in ver_bytes:
                    ver_bytes = ver_bytes.split(b"\x00")[0]
                return ver_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            log.error(f"Failed to parse bin version: {e}")
        return "Unknown"

    def _select_firmware(self):
        path = filedialog.askopenfilename(filetypes=[("Firmware binary", "*.bin")])
        if path:
            self._ota_path_var.set(path)
            ver = self._read_bin_version(path)
            self._ota_bin_ver_text.set(f"Selected Bin Version: {ver}")

    def _start_ota(self):
        if not self._connected:
            messagebox.showerror("Error / 错误", "Please connect to the device over USB serial first!\n请先连上有线串口！")
            return
        path = self._ota_path_var.get()
        if not path or not os.path.exists(path):
            messagebox.showerror("Error / 错误", "Please select a valid firmware (.bin) file!\n请先选择有效的 .bin 固件文件！")
            return
            
        self._set_ui_state(tk.DISABLED)
        self._ota_status_text.set("OTA Initializing...")
        _run_async(self._do_ota(path))

    def _set_ui_state(self, state):
        self._ota_select_btn.configure(state=state)
        self._ota_flash_btn.configure(state=state)
        self._write_btn.configure(state=state)
        self._conn_btn.configure(state=state)
        self._port_combo.configure(state="readonly" if state == tk.NORMAL else state)
        for btn in self._cap_btns:
            if btn:
                btn.configure(state=state)

    async def _do_ota(self, bin_path):
        def progress_cb(written, total):
            pct = (written / total) * 100
            self.root.after(0, lambda: self._ota_progress_var.set(pct))
            self.root.after(0, lambda: self._ota_status_text.set(
                f"Flashing: {written}/{total} bytes ({pct:.1f}%)"
            ))

        ok = await self.spp.upload_firmware(bin_path, progress_cb)
        if ok:
            self.root.after(0, lambda: messagebox.showinfo(
                "Success / 成功", 
                "Firmware OTA flash completed successfully!\n"
                "The board is rebooting now. Please wait a few seconds and reconnect.\n\n"
                "固件升级成功！开发板正在重新启动，请稍后重新刷新并连接串口。"
            ))
            self.root.after(0, lambda: self._disconnect())
            self.root.after(0, lambda: self._ota_status_text.set("OTA Success! Rebooted."))
        else:
            self.root.after(0, lambda: messagebox.showerror(
                "Error / 错误", 
                "OTA Firmware flashing failed!\n固件升级失败！请重试。"
            ))
            self.root.after(0, lambda: self._ota_status_text.set("OTA Failed."))
            
        self.root.after(0, lambda: self._set_ui_state(tk.NORMAL))

    # ── Callbacks (from Serial Client) ────────────────────────────
    def _on_button_event(self, btn_id: int, state: int):
        self.root.after(0, lambda: self._handle_button_event(btn_id, state))

    def _handle_button_event(self, btn_id: int, state: int):
        s = "PRESSED / 按下" if state == 1 else "RELEASED / 松开"
        self._last_event_text.set(f"Button {btn_id + 1} {s}")

    def _on_status(self, hfp: int, audio: int):
        self.root.after(0, lambda: self._handle_status(hfp, audio))

    def _handle_status(self, hfp: int, audio: int):
        hfp_s = "Connected / 已连接" if hfp else "--"
        audio_s = "Active / 活跃" if audio else "--"
        self._hfp_label.configure(text=f"HFP: {hfp_s}")
        self._audio_label.configure(text=f"Audio: {audio_s}")

    # ── Cloud update & OTA operations ─────────────────────────────
    async def _check_github_version(self):
        url = "https://api.github.com/repos/elementchen/VoxTriple_Classic/releases/latest"
        headers = {"User-Agent": "VoxTriple-App"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read().decode())
            data = json.loads(response)
            
            tag_name = data.get("tag_name", "")
            version_str = tag_name.lstrip("v")
            
            bin_url = None
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.startswith("esp32_bt_mic_v") and name.endswith(".bin") and "merged" not in name:
                    bin_url = asset.get("browser_download_url")
                    break
            
            if version_str and bin_url:
                self._github_version = version_str
                self._github_bin_url = bin_url
                self.root.after(0, self._compare_and_update_version_ui)
        except Exception as e:
            log.error(f"Failed to check GitHub version: {e}")

    def _compare_and_update_version_ui(self):
        # Clean existing dynamic labels and buttons
        self._new_ver_label.pack_forget()
        self._update_btn.pack_forget()
        
        if not self._connected or not self._board_version or not self._github_version:
            return
            
        try:
            # Parse semantic version (e.g. 1.0.3 -> [1, 0, 3])
            local_parts = [int(x) for x in self._board_version.split(".") if x.isdigit()]
            cloud_parts = [int(x) for x in self._github_version.split(".") if x.isdigit()]
            
            if cloud_parts > local_parts:
                self._new_ver_label.configure(text=f"(最新版: {self._github_version})", foreground="#d35400")
                self._new_ver_label.pack(side="left", padx=8)
                self._update_btn.pack(side="left", padx=8)
            else:
                self._new_ver_label.configure(text="(已经是最新版固件)", foreground="#16a085")
                self._new_ver_label.pack(side="left", padx=8)
        except Exception as e:
            log.error(f"Version comparison failed: {e}")
            # Fallback comparison
            if self._github_version != self._board_version:
                self._new_ver_label.configure(text=f"(最新版: {self._github_version})", foreground="#d35400")
                self._new_ver_label.pack(side="left", padx=8)
                self._update_btn.pack(side="left", padx=8)
            else:
                self._new_ver_label.configure(text="(已经是最新版固件)", foreground="#16a085")
                self._new_ver_label.pack(side="left", padx=8)

    def _on_update_clicked(self):
        if not self._connected or not self._github_version:
            return
        
        # Shift to Tab 2
        self._notebook.select(1)
        
        # Start smart upgrade
        self._set_ui_state(tk.DISABLED)
        self._ota_status_text.set("Initializing smart update...")
        _run_async(self._do_smart_update())

    async def _do_smart_update(self):
        cache_dir = "cache"
        os.makedirs(cache_dir, exist_ok=True)
        filename = f"esp32_bt_mic_v{self._github_version}.bin"
        save_path = os.path.join(cache_dir, filename)
        
        # Check cache
        if os.path.exists(save_path):
            self.root.after(0, lambda: self._ota_status_text.set("Found cached bin. Flashing..."))
        else:
            # Download from GitHub
            self.root.after(0, lambda: self._ota_status_text.set("Downloading latest firmware..."))
            try:
                await self._download_firmware(self._github_bin_url, save_path)
            except Exception as e:
                log.error(f"Download failed: {e}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error / 错误", 
                    f"Failed to download firmware from GitHub:\n{e}\n\n下载最新固件失败，请检查网络！"
                ))
                self.root.after(0, lambda: self._ota_status_text.set("Download failed."))
                self.root.after(0, lambda: self._set_ui_state(tk.NORMAL))
                return
                
        # Trigger OTA flash
        self.root.after(0, lambda: self._ota_status_text.set("Flashing downloaded firmware..."))
        await self._do_ota(save_path)

    async def _download_firmware(self, download_url, save_path):
        loop = asyncio.get_event_loop()
        def do_download():
            req = urllib.request.Request(download_url, headers={"User-Agent": "VoxTriple-App"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                bytes_read = 0
                with open(save_path, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_read += len(chunk)
                        if total_size > 0:
                            pct = (bytes_read / total_size) * 100
                            self.root.after(0, lambda p=pct: self._ota_progress_var.set(p))
                            self.root.after(0, lambda b=bytes_read, t=total_size, p=pct: self._ota_status_text.set(
                                f"Downloading: {b}/{t} bytes ({p:.1f}%)"
                            ))
        await loop.run_in_executor(None, do_download)

    def _on_close(self):
        keyboard_io.stop_key_capture()
        if self._connected:
            _run_async(self.spp.disconnect())
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
