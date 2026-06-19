# 纯 NimBLE BLE 键盘稳定重连里程碑总结 (NimBLE Stable Milestone)

本篇文档总结了我们在纯 NimBLE 键盘测试分支（`test-bt53-coexist`）上，为解决“设备识别混淆”、“冷置超时断连”、“重启重连闪退（MIC Failure）”以及“启动无广播”所进行的全部根源剖析与终极修复。

这些优化不仅让设备达到了**100% 自动秒连、绝不闪退、闲置不掉线**的完美状态，而且其中的设计原理对于我们下一步向 **Bluedroid 协议栈**迁移以及未来其它任何蓝牙协议栈的开发，都具有极其关键的指导和借鉴意义。

---

## 1. 核心修复与技术借鉴价值

### A. GAP 服务描述符的显式更新 (解决首次连接识别为 NIMBLE 且图标错误)
* **问题现象**：设备首次配对时在 Windows 蓝牙列表中显示为 `NIMBLE`（且图标为普通设备，非键盘）。只有重启或在设备管理中更新缓存后，才勉强识别为键盘。
* **技术根源**：虽然我们在广播数据包中正确声明了设备名和键盘外观 (`0x03C1`)，但在蓝牙连接建立的瞬间，Windows 底层驱动会直接拉取 GATT 的 GAP 属性中的 `Device Name Characteristic` 和 `Appearance Characteristic`。若不显式更新这两个属性，它们依旧保持 NimBLE 协议栈默认的 `"nimble"` 和 `"0"`，导致 Windows 判定设备属性错误。
* **解决与借鉴**：
  在 `app_main` 启动主机前，必须显式调用 GAP 服务属性设置函数：
  ```c
  ble_svc_gap_device_name_set(dev_name);
  ble_svc_gap_device_appearance_set(ESP_HID_APPEARANCE_KEYBOARD); // 0x03C1
  ```
  **💡 跨平台/跨协议栈借鉴**：不论使用什么协议栈，均需保证 GATT 基础 GAP 服务的 `Device Name` 和 `Appearance` 与广播包完全匹配，Windows 等严格的主机端才能在首次发现时给出正确的设备图标与名称。

### B. 彻底禁用 Modem Sleep 防止时钟温飘 (解决冷置超时断联 reason=546)
* **问题现象**：连接在闲置几分钟后，串口突发 `disconnect; reason=546`（LMP 连接超时错误）并断开。
* **技术根源**：固件底层默认开启了蓝牙控制器的低功耗睡眠模式（`Modem Sleep`）。在无按键交互的闲置期间，Controller 会休眠并切换至 150kHz 的 RC 慢速内部时钟。然而内部时钟由于精度低且受温度漂移影响较大，长时休眠后唤醒，ESP32 无法精准卡入 Windows 发送的 Connection Event 射频时隙，造成严重的物理层连续丢包，被主机强制断连。
* **解决与借鉴**：
  在 `sdkconfig` 中硬性禁用低功耗休眠，使控制器和高精度 RF 时钟始终以 100% 满频运行：
  ```ini
  # CONFIG_BTDM_CTRL_MODEM_SLEEP is not set
  # CONFIG_BTDM_CTRL_MODEM_SLEEP_MODE_ORIG is not set
  # CONFIG_BTDM_CONTROLLER_MODEM_SLEEP is not set
  ```
  同时在代码中显式调用 API 禁用蓝牙休眠（以防运行时配置被重置）：
  ```c
  esp_bt_sleep_disable();
  ```
  **💡 跨平台/跨协议栈借鉴**：对于按键这种高实时性、无稳定物理保活心跳的设备，低功耗睡眠时钟精度是致命隐患。在使用 Bluedroid 等其它协议栈时，同样必须关闭控制器睡眠，或确保外部接有高精度的 32.768kHz 晶振（硬件补偿）。

### C. 强制进行 ENC 密钥分发声明 (解决重启自动重连失效与 573 闪退)
* **问题现象**：重启 ESP32 后，自动重连彻底失效；或者重连时必定经历一次或多次 `status=7 / reason=573` (MIC Failure) 报错断连。
* **技术根源**：
  1. **重连失效**：虽然 Secure Connections (SC) 模式会通过 ECDH 自动生成 LTK，但 Windows 规定在配对的 Phase 3 密钥分发（Key Distribution）阶段，必须看到 Encryption Key (`BLE_SM_PAIR_KEY_DIST_ENC`) 的分发声明。如果将其剥离，Windows 会判定此连接无须持久化绑定，配对结束后直接丢弃 LTK，重启后自然无法重连。
  2. **重连 573 闪断**：由于 Modem Sleep 引起时钟偏差，重启重连时前几次握手极易发生丢包，引起解密计数器（Packet Counter）错位，底层直接报 MIC 校验错误。
* **解决与借鉴**：
  在配置安全参数时，必须保留并声明 ENC 分发：
  ```c
  ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ```
  同时结合禁用 `Modem Sleep`，消除了时钟漂移，使重连直接通过 `status=0` 极速完成。
  **💡 跨平台/跨协议栈借鉴**：Windows 的蓝牙安全子系统对输入设备（HID）的 Bonding 持久化有极其严苛的要求。在后续的 Bluedroid 键盘开发中，我们必须遵循同样的原则，在安全配对响应中开启完整的加密绑定分发标志。

### D. 回调挂载时序调整 (解决启动无广播)
* **问题现象**：编译烧录后，设备初始化卡死在 NimBLE 任务开启，始终无法向外发出广播。
* **技术根源**：`esp_hid_gap_init()` 内部初始化 NimBLE 协议栈时会重置并清空全局配置 `ble_hs_cfg`。如果提前在 `main.c` 注册了 `sync_cb = nimble_on_sync`，它就会被悄无声息地覆盖为 `NULL`，导致协议栈就绪后没有执行我们的广告启动函数。
* **解决与借鉴**：
  将所有 `ble_hs_cfg` 属性设置（包括 NVS 读取与 `sync_cb`）严格移至 `esp_hid_gap_init()` 和 `esp_hid_ble_gap_adv_init()` 之后执行：
  ```c
  esp_hid_gap_init(HID_DEV_MODE);
  esp_hid_ble_gap_adv_init(ESP_HID_APPEARANCE_KEYBOARD, dev_name);
  
  // 必须在此之后挂载回调
  ble_hs_cfg.store_read_cb = my_store_read_cb;
  ble_hs_cfg.sync_cb = nimble_on_sync;
  ```

---

## 2. 演进路线规划 (小步慢跑)

我们将遵循以下策略平稳推进至双模共存：
1. **纯 NimBLE 完美秒连键盘**（已完成并归档）。
2. **纯 Bluedroid BLE 键盘迁移**（当前进行中，隐藏经典蓝牙，对齐时钟、密钥配置，验证直通模式）。
3. **经典蓝牙 HFP 双模叠加**（验证稳定后，开启 `ENABLE_CLASSIC_BT_MIC`，测试两者共存重连）。
