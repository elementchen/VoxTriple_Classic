# VoxTriple — ESP32 Bluetooth HID Keyboard & HFP Microphone System<br/>ESP32 蓝牙 HID 键盘与 HFP 麦克风系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Build](https://img.shields.io/badge/build-ESP--IDF%205.5-blue.svg)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/index.html)
[![Python](https://img.shields.io/badge/app-Python%203-green.svg)](https://www.python.org/)

> An ESP32-based multi-mode Bluetooth system providing a classic Bluetooth HID Keyboard and an HFP Hands-Free Client (Microphone) simultaneously. Includes programmable key mapping, wired ultra-fast OTA updating, and modern native companion apps for Windows and macOS.
>
> 基于 ESP32 的多模蓝牙系统。同时拉起经典蓝牙 HID 键盘与 HFP 免提客户端（麦克风）双重角色。支持自定义按键映射配置、20秒极速有线 OTA 升级机制，并配套提供适用于 Windows 和 macOS 的现代原生配置客户端。

----

## Features / 功能特性

- **Dual-Profile Bluetooth** — Act as a Bluetooth HID Keyboard and an HFP Hands-Free Client simultaneously. Windows and macOS recognize it natively as a keyboard and an audio input device. No drivers needed.
  
  **经典蓝牙多协议共存** — 同时扮演经典蓝牙 HID 键盘与 HFP 免提客户端（麦克风）双重 Profile（即多协议复合设备）。系统原生免驱识别为音频输入设备与实体键盘。

- **Teal Visual & Dotted Focus-Free UI** — Sleek card-layout desktop companion applications designed in native Python Tkinter. 100% free of dotted focus rings and fully integrated with OS style behaviors.
  
  **卡片式无虚线原生 UI** — 基于 Python Tkinter 匠心设计的卡片式配置客户端，彻底铲除点击时难看的焦点虚线框，完美融合系统原生外观（提供直观的蓝色勾选框 ☒ 交互）。

- **20s Ultra-Fast Wired OTA** — Dedicated C-level hardware console driver registry bypassing VFS serial line filters. Transfers `.bin` firmware data lossless in 1024-byte aligned blocks. OTA upgrade completes in 20-30 seconds with automatic verification and soft reboot.
  
  **20秒极速有线 OTA** — 固件端注册硬件级串口中断驱动并进行重定向，100% 物理绕过 VFS 的控制字符拦截（防止 `Ctrl+C` 等引起字节丢失）。支持 1024 字节大块对齐与硬件级自动冲刷校验，20秒闪电完成升级并自动重启。

- **Version-Stamped Releases** — Build system automatically extracts the firmware version during build time and duplicates a version-stamped binary (e.g., `esp32_bt_mic_v1.0.3.bin`) to prevent compiler overwrites.
  
  **版本自动命名** — 编译时自动从代码中提取当前版本号，在 `build/` 目录下复制出一份带有版本戳的固件（如 `esp32_bt_mic_v1.0.3.bin`），防止重复编译覆盖，方便 GitHub Releases 归档。

- **Cross-Platform Config Apps** — 
  - **Windows App**: Communication via Bluetooth SPP Serial (COM), featuring live physical key press monitor with highlight colors.
  - **macOS App**: Control over Bluetooth BLE GATT, using Apple Accessibility features to capture keystrokes.
  
  **跨平台配置客户端** —
  - **Windows 客户端**: 通过经典蓝牙虚拟串口（SPP COM）有线/无线通信，内置大字号物理按键按下事件监控器。
  - **macOS 客户端**: 通过 BLE GATT 无线修改键值，联动 macOS 系统辅助功能进行键值捕获。

- **mSBC Wideband Speech** — 16 kHz wideband speech pipeline with DSP audio processing (moving average + high-pass filtering). Realizes telephone-grade crisp speech input.
  
  **mSBC 宽带语音** — 16kHz 采样率的高清录音通道，内置 DSP 算法（滑动平均降噪 + 高通滤波滤除低频杂音）。提供高清晰度的语音输入。

---

## Hardware / 硬件清单

| Component 组件 | Model 型号 | Qty 数量 |
|---------------|-----------|---------|
| Dev Board 开发板 | NodeMCU-32S (ESP32-WROOM-32) | 1 |
| Microphone 麦克风 | INMP441 MEMS I2S module | 1 |
| Buttons 按钮 | 6×6mm tactile switch / 轻触开关 | 4 |
| LED 指示灯 | Blue LED / 蓝色 3mm 发光二极管 | 1 |

---

## Wiring / 接线说明

```
INMP441 (麦克风) → ESP32:
  VDD  → 3.3V          Never connect to 5V! / 严禁接 5V！
  GND  → GND
  L/R  → GND           Left channel / 必须接地设为左声道
  SD   → GPIO 17       I2S Serial Data (SD)
  WS   → GPIO 22       Word Select (LRC / WS)
  SCK  → GPIO 21       Serial Clock (BCLK / SCK)

Buttons (按键) → ESP32:
  Button 1 → GPIO 4     Key 1 (Default: Enter / 回车)
  Button 2 → GPIO 16    Key 2 (Default: Esc / 退出)
  Button 3 → GPIO 19    Key 3 (Default: Space / 空格)
  Button 4 → GPIO 23    Key 4 (Default: Tab / 制表键) [长按 3 秒擦除蓝牙绑定并重启]

Status LED (录音状态指示灯) → ESP32:
  Anode (正极)   → GPIO 18    Connect a 220Ω current-limiting resistor / 经 220Ω 限流电阻接 GPIO
  Cathode (负极) → GND

* All buttons are active-low (GPIO → Button → GND) with internal pull-up enabled.
* 所有按键均为低电平有效，接线方式为 GPIO 引脚接按键再到 GND，使用内部上拉。
```

---

## Setup & Flash Guide / 固件编译烧录

### 1. Initialize ESP-IDF Environment
Ensure you have ESP-IDF v5.5.1 installed. Start your terminal (e.g. PowerShell) and run:
确保您已安装 ESP-IDF v5.5.1。启动终端，执行：

```powershell
$env:IDF_PATH="C:\Espressif\frameworks\esp-idf-v5.5.1"
. C:\Espressif\Initialize-Idf.ps1
```

### 2. Build & Flash
Navigate to the `esp32_bt_mic` workspace. Build and flash target hardware at a highly stable **115200** baud rate to isolate potential channel line noise:
切换至 `esp32_bt_mic` 文件夹。为了彻底隔离阻抗线路噪声，建议使用 **115200** 稳定波特率进行烧写：

```powershell
cd esp32_bt_mic
# Build project
idf.py build

# Flash at 115200 baud
idf.py -p COM5 -b 115200 flash
```

---

## Configuration Apps Guide / 配置客户端使用说明

### 1. Windows Companion App (SPP 有线/无线)
Located under `windows_app_python/`. Runs natively on Python 3.
位于 `windows_app_python/` 目录下，基于 Python 3。

#### Requirements & Setup
```powershell
cd windows_app_python
pip install -r requirements.txt
python vox_triple.py
```

#### standalone EXE compilation
We support compiling the app into a single standalone, DLL-free `.exe` file. Install `PyInstaller` and compile:
本客户端支持一键打包为独立的免依赖 `.exe` 应用程序。执行以下指令完成编译：

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name="VoxTripleConfig" vox_triple.py
# Output path / 输出目录: windows_app_python/dist/VoxTripleConfig.exe
```

#### App Tabs Details
- **Keyboard Config (键盘配置)**: Key mapping, TX power levels, and sleep toggles. Apply configuration wirelessly or via USB instantly (Hot Update).
- **Firmware OTA (固件升级)**: Double-row aligned OTA interface. Select a target bin file, view extracted version numbers, and click to update.
- **Info (说明书)**: Built-in help and user manual.

---

### 2. macOS Companion App (BLE GATT 无线)
Located under `MAC_app_python/`. Controls the device completely over Bluetooth low energy.
位于 `MAC_app_python/` 目录下，直接通过低功耗蓝牙无线改键。

#### Setup
```bash
cd MAC_app_python
pip install -r requirements.txt
python3 vox_triple_mac.py
```

> [!IMPORTANT]
> macOS keypress hook requires **Accessibility Permission** in macOS system settings:
>
> macOS 下键盘按键捕获需要您开启**系统辅助功能权限**：
> `系统设置` → `隐私与安全性` → `辅助功能`，添加终端或此程序并允许。

---

## Project Directory Structure / 项目结构

```
VoxTriple/
├── esp32_bt_mic/                  # ESP32 firmware / ESP32 固件 (ESP-IDF 5.5)
│   ├── CMakeLists.txt
│   ├── partitions.csv             # Custom partition table (OTA_0, OTA_1, NVS)
│   ├── sdkconfig.defaults         # Config defaults for Dual-profile BT & SPP
│   └── src/
│       ├── main.c                 # Entry / 初始化入口
│       ├── bt_init.c              # Bluetooth stack & Controller configurations
│       ├── bt_hfp_hf.c            # HFP Client & SCO wideband speech logic
│       ├── classic_hidd.c         # Classic Bluetooth HID Keyboard descriptors & events
│       ├── spp_server.c           # Bluetooth Classic SPP command channel
│       ├── uart_console.c         # Wired hardware Console UART driver & 20s OTA engine
│       ├── config_cmd.c           # Common configuration parser (cJSON-based)
│       ├── audio_capture.c        # I2S legacy microphone driver for INMP441
│       └── config_storage.c       # Non-volatile storage (NVS) read/write
│
├── windows_app_python/            # Windows config App / Windows 客户端 (SPP)
│   ├── vox_triple.py              # Main GUI script / 界面主入口
│   ├── spp_client.py              # Asynchronous SPP packet stream controller
│   ├── config_service.py          # Persistence storage service
│   ├── keyboard_io.py             # Win32 key hooks and display formatter
│   └── requirements.txt
│
└── MAC_app_python/                # macOS config App / macOS 客户端 (BLE GATT)
    ├── vox_triple_mac.py          # Main GUI script
    ├── keyboard_io_mac.py         # macOS accessibility key capture hook
    └── requirements.txt
```

---

## License / 许可证
MIT License © 2024-2026
