# VoxTriple — ESP32 3-Button Bluetooth PTT Microphone<br/>ESP32 三键蓝牙 PTT 麦克风

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PlatformIO](https://img.shields.io/badge/build-PlatformIO-orange.svg)](https://platformio.org/)
[![.NET](https://img.shields.io/badge/app-.NET%208-purple.svg)](https://dotnet.microsoft.com/)

> An ESP32-based Bluetooth microphone system with three physical buttons: programmable keyboard shortcuts. Button 1 also drives a simple GPIO indicator LED. Designed for Windows voice input.
>
> 基于 ESP32 的蓝牙麦克风系统。三键物理按钮均可编程为键盘快捷键，Button 1 同时驱动 GPIO 指示灯。专为 Windows 语音输入（语音识别 / 讯飞）设计。

----

## Features / 功能特性

- **Bluetooth Microphone** — ESP32 acts as an HFP Hands-Free Client. Windows recognizes it natively as a Bluetooth audio input device. No driver needed.
  
  **蓝牙麦克风** — ESP32 扮演 HFP Hands-Free Client 角色，Windows 原生识别为蓝牙音频输入设备，免驱即用。

- **Indicator LED** — Button 1 drives a simple GPIO LED on GPIO 26. Press to light up, release to turn off.

  **指示灯** — Button 1 驱动 GPIO 指示灯（GPIO 26）。按下点亮，松开熄灭。

- **Programmable Shortcuts** — All 3 buttons can be mapped to any Windows key combination including modifiers (Ctrl / Shift / Alt / Win). Configurable wirelessly.

  **可编程快捷键** — 3 个按钮均可映射任意键盘组合键（含 Ctrl/Shift/Alt/Win 修饰键），通过 BLE 无线配置。

- **BLE Wireless Config** — A companion Windows WPF app reads and writes button mappings over BLE GATT in real time. No need to reflash the ESP32 to change shortcuts.

  **BLE 无线配置** — Windows WPF 配置应用通过 BLE GATT 实时读写按钮映射。改快捷键不需要重新烧录 ESP32。

- **Auto-start & Auto-connect** — The Windows app optionally starts with Windows, then automatically scans for and reconnects BLE. Classic Bluetooth (HFP) reconnects automatically after the first pairing.

  **开机自动连接** — Windows 应用可设置为开机自启动，启动后自动扫描并连接 BLE。经典蓝牙（HFP）首次配对后自动重连。

- **mSBC Wideband Speech** — 16 kHz sampling with on-device noise-reduction DSP (high-pass filter + moving average). Clean voice input at telephone-grade quality.

  **mSBC 宽带语音** — 16kHz 采样，板载降噪 DSP（高通滤波 + 滑动平均）。提供电话级清晰度的语音输入。

- **Single-file EXE** — The Windows app can be published as a single standalone `.exe` with no DLL dependencies.

  **单文件 EXE** — Windows 应用可发布为单个 `.exe` 文件，无需附带任何 DLL。

## Hardware / 硬件清单

| Component 组件 | Model 型号 | Qty 数量 |
|---------------|-----------|---------|
| Dev Board 开发板 | NodeMCU-32S (ESP32-WROOM-32) | 1 |
| Microphone 麦克风 | INMP441 MEMS I2S module | 1 |
| Buttons 按钮 | 6×6mm tactile switch / 轻触开关 | 3 |
| Capacitor (optional) 电容(可选) | 100nF ceramic for hardware noise reduction / 瓷片电容用于硬件降噪 | 1 |

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
  Button 4 → GPIO 23    Key 4 (Default: Tab / 制表键) [长按3秒清除绑定并重启]

Status LED (录音状态指示灯) → ESP32:
  Anode (正极)   → GPIO 18    via a 220Ω current-limiting resistor / 经 220Ω 限流电阻
  Cathode (负极) → GND

* All buttons are active-low (GPIO → Button → GND) with internal pull-up enabled.
* 所有按键均为低电平有效，接线方式为 GPIO 引脚接按键再到 GND，使用内部上拉。
```

## Quick Start / 快速开始

### 1. Build & Flash Firmware / 编译烧录固件

```bash
pip install platformio
cd esp32_bt_mic
pio run -t upload --upload-port COM4
```

### 2. Pair Bluetooth / 蓝牙配对

Open Windows Bluetooth settings → Add device → look for `ESP32_BT_MIC_XX` (where `XX` is the last two hex digits of the board's MAC address) → pairing is automatic via SSP

打开 Windows 蓝牙设置 → 添加设备 → 搜索 `ESP32_BT_MIC_XX`（`XX` 为板子 MAC 地址末两位十六进制）→ SSP 自动配对，无需输入配对码

### 3. Build & Run Config App / 编译运行配置应用

```bash
cd windows_app
dotnet run --project Esp32BtMicConfig
```

To produce a single-file `.exe` （打包为单文件 EXE）:

```bash
cd windows_app/Esp32BtMicConfig
dotnet publish -r win-x64 -c Release -p:PublishSingleFile=true --self-contained false -o publish
# Output / 输出: publish/Esp32BtMicConfig.exe (~25 MB)
```

### 4. Daily Use / 日常使用

1. **Bluetooth Pairing (蓝牙配对)**: Pair the device `ESP32_BT_KBD_MIC_XX` from Windows settings. The keyboard profile and microphone profile are both configured automatically.
   打开 Windows 蓝牙设置配对 `ESP32_BT_KBD_MIC_XX`。配对成功后，蓝牙键盘与麦克风设备都将由系统自动安装并就绪。
2. **Keyboard Config (快捷键改键配置)**: Open the Windows companion WPF app. It automatically connects over BLE and allows mapping Buttons 1-4 to any Virtual-Key codes or modifiers.
   打开 Windows WPF 配置应用。它会自动通过 BLE 连接开发板，并允许为按键 1-4 映射任意的键盘键码及修饰键组合。
3. **Always-On Mic (免按键常开麦克风)**: The microphone channel (SCO) connects automatically whenever the device pairs/reconnects. You can speak instantly into Windows Speech Recognition or voice input apps without pressing physical buttons. The status LED (GPIO 18) stays solid while recording.
   设备连入电脑后，麦克风（SCO 通道）会自动发起连接并保持常开。您可以直接使用 Windows 语音输入或各类语音软件，无需物理按压任何按键。录音时状态指示灯（GPIO 18）常亮。
4. **Physical Keypress Reconnect (随点随连)**: If you restart the ESP32 or lose connection, press **any of the 4 buttons** to trigger a fast reconnect to the host.
   当开发板重启或发生断连时，**按下 1-4 键的任意一个键**，都会在后台立即向电脑发起重连呼叫，保障键盘和麦克风快速连回。
5. **Reset Pairing (重置配对)**: Hold **Button 4** for 3 seconds to clear paired links and reset configurations to default.
   长按 **按键 4** 达 3 秒即可自动擦除已配对的蓝牙主机信息并恢复出厂设置。

## Project Structure / 项目结构

```
VoxTriple/
├── esp32_bt_mic/              # ESP32 firmware / ESP32 固件 (PlatformIO + ESP-IDF 5.5)
│   ├── platformio.ini
│   ├── sdkconfig.defaults     # BTDM dual-mode + HFP HF Client + BLE
│   ├── partitions.csv
│   └── src/
│       ├── main.c                       # Entry point / 入口
│       ├── bt_init.c/h                  # BT init + GAP / 蓝牙初始化
│       ├── bt_hfp_hf.c/h                # HFP HF Client + SCO audio pipeline
│       ├── bt_app_core.c/h              # BT task dispatcher / 蓝牙任务分发
│       ├── bt_app_hf.c/h                # HFP callback / HFP 回调
│       ├── ble_gatts_config.c/h         # BLE GATT service (0x1820) / BLE 服务
│       ├── audio_capture.c/h            # I2S INMP441 driver (legacy) / I2S 驱动
│       ├── button_handler.c/h           # Button debounce + PTT / 按钮消抖
│       └── config_storage.c/h           # NVS config storage / NVS 配置存储
│
├── windows_app/               # Windows config app / Windows 配置应用 (.NET 8 WPF)
│   └── Esp32BtMicConfig/
│       ├── Services/
│       │   ├── BleGattClient.cs         # BLE scan / connect / R/W / BLE 扫描连接读写
│       │   ├── KeyboardSimulator.cs     # keybd_event keyboard simulation / 键盘模拟
│       │   └── ConfigurationService.cs  # JSON config persistence / JSON 配置持久化
│       ├── ViewModels/MainViewModel.cs  # MVVM ViewModel
│       └── Views/MainWindow.xaml/cs     # UI + Win32 key capture hook / 主界面
│
└── docs/
    ├── architecture.md         # System architecture / 系统架构
    ├── ble_protocol.md         # BLE GATT protocol specification / BLE 协议规范
    └── wiring_diagram.txt      # Detailed wiring diagram / 详细接线图
```

## BLE Protocol / BLE 协议

The ESP32 exposes a custom GATT service for button configuration. The Windows app communicates with the ESP32 over BLE to read and write button mappings in real time.

ESP32 暴露出一个自定义 GATT 服务用于按钮配置。Windows 应用通过 BLE 与 ESP32 通信，实时读写按钮映射。

- **Service UUID / 服务 UUID**: `0x1820` (00001820-0000-1000-8000-00805F9B34FB)
- **Button 1-3 Map / 按钮 1-3 映射** (0x2A01-0x2A03): Read/Write, `[vk_code:u8, modifier:u8]`
  - `vk_code` — Windows Virtual-Key code (e.g. 0x0D = Enter, 0x09 = Tab) / Windows 虚拟键码
  - `modifier` — Modifier key bitmask (see below) / 修饰键位掩码（见下表）
- **Button Event / 按钮事件** (0x2A04): Notify, `[button_id:u8, state:u8]`
  - Sent whenever a physical button is pressed (state=1) or released (state=0) / 物理按钮按下(1)或松开(0)时发送
- **Device Status / 设备状态** (0x2A05): Notify, `[hfp_connected:u8, audio_active:u8]`

Modifier key bitmask / 修饰键位掩码:

| Bit | Key |
|-----|-----|
| 0 | Left Ctrl |
| 1 | Left Shift |
| 2 | Left Alt |
| 3 | Left Win |
| 4 | Right Ctrl |
| 5 | Right Shift |
| 6 | Right Alt |
| 7 | Right Win |

## Tech Stack / 技术栈

| Component 组件 | Technology |
|---------------|------------|
| MCU 芯片 | ESP32 (Xtensa LX6, 240 MHz) |
| Firmware Framework 固件框架 | ESP-IDF 5.5 / PlatformIO |
| Bluetooth Stack 蓝牙协议栈 | Bluedroid BTDM (Classic + BLE dual-mode) |
| Audio Codec 音频编解码 | HFP mSBC 16 kHz WBS (Wideband Speech) |
| Mic Driver 麦克风驱动 | I2S Legacy Driver (`driver/i2s.h`) |
| Desktop App 桌面应用 | .NET 8 WPF + CommunityToolkit.Mvvm |
| Keyboard Simulation 键盘模拟 | Win32 `keybd_event` API |
| BLE Scanning BLE 扫描 | `BluetoothLEAdvertisementWatcher` (Active mode) |

## License / 许可证

MIT License © 2024-2026
