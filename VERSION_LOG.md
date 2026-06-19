# Version Log

## v2.2-nimble-stable | 2026-06-19

- **Branch**: `test-bt53-coexist`
- **Commit**: `85c8c05`
- **特点**: 纯 NimBLE BLE 键盘完美自动秒连版本，解决了配对混淆、时钟温飘断连、重连 573 闪退及启动挂死问题，为后续协议栈重构奠定理论基线。

### 核心优化
- **GAP描述符更新**: 显式配置 GAP Device Name 和 Appearance (0x03C1)，确保 Windows 首次配对成功显示“键盘”图标。
- **禁用 Modem Sleep**: 运行时调用 `esp_bt_sleep_disable()` 并硬性禁用控制器休眠，避免 RC 慢速时钟温飘导致冷置 LMP 连接超时 (reason=546)。
- **密钥分配对齐**: 保持 `ENC_KEY` 分发声明，使 Windows 底层顺利执行 Bonding 密钥持久化，规避重启重连失效问题。
- **回调挂载时序**: 将 `sync_cb` 挂载移到 `esp_hid_gap_init` 之后，防止被协议栈重置逻辑覆盖导致启动无广告广播。

---

## v1.7-stable | 2026-05-28

- **Branch**: `master`
- **Commit**: `1e9ebf3`

### ESP32 固件
- **4 按键支持**：所有功能引脚集中到 NodeMCU-32S 右侧排 (J2)
  - Button 1: GPIO4 (J2-13), Button 2: GPIO16 (J2-12)
  - Button 3: GPIO19 (J2-8), Button 4: GPIO23 (J2-2)
  - LED 指示灯: GPIO18 (J2-9), 仅 BLE 连接时按下 Button 1 亮起
  - I2S: BCK=GPIO21(J2-6), WS=GPIO22(J2-3), DATA=GPIO17(J2-11)
  - 3V3: J1-1（唯一左侧引线）
- **BLE GATT 扩展**: 0x2A06 (TX Power), 0x2A07 (Sleep Mode), 0x2A08 (Button 4)
  - GATTS_NUM_HANDLES 16→24 修复特性分配失败
- **音频增益**: 3x 数字增益 (~+9.5dB) 提升麦克风音量
- **WiFi 禁用**: 启动时关闭 WiFi 省电
- **默认值**: TX Power 0dBm, Sleep Mode 启用

### Python 应用 (VoxTriple.exe)
- Button 4 完整 UI 支持（捕获按键、修饰键、读写设备）
- TX Power 下拉框 + Sleep Mode 复选框
- 写入设备后 3 秒自动恢复连接状态显示
- Combobox 绑定修复 (IntVar → Combobox.current())
- 窗口高度 840px 适配 4 按键布局

### PCB
- `_PCB/board_layout.md` — 完整焊盘定位和布线指南
- `_PCB/VoxTriple.kicad.net` — KiCAD 标准库封装网表

---

## v1.1-stable | 2026-05-14

- **Commit**: `f36d688`
- **Message**: v1.1-stable: simplified architecture, zero task_wdt, rainbow LED, Python app
