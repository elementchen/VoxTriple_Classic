# ESP32 蓝牙技术演进与防踩坑记录 (Cumulative Version Evolution & Pitfalls)

本篇文档用于记录本项目从纯键盘到双模共存的演进历史。采用**增量追加模式**，记录每个重要版本的核心改动、遇到的关键缺陷（坑）、以及最终采取的消解方案，以便防微杜渐，避免历史问题重复发生。

---

## [v2.3-bluedroid-ble-only] 纯 Bluedroid BLE 键盘验证版本 | 2026-06-19

- **协议栈**: Bluedroid
- **状态**: 纯 BLE 键盘 (ENABLE_CLASSIC_BT_MIC = 0)
- **目标**: 在 Bluedroid 下实现与 NimBLE 同样稳定的首次配对和自动秒连重连。

### 踩坑 1：Windows 首次配对无法正确识别为“键盘”图标
* **故障现象**: Windows 搜索到设备并配对后，设备列表里只显示普通通用设备图标，偶尔识别为键盘。
* **原因分析**: Bluedroid 中仅在广播包中设置外观 `appearance = 0x03C1` 是不够的。Windows 首次连接建立时会去读取 GATT GAP 服务（Generic Access Service, UUID `0x1800`）下的 `Appearance Characteristic` (UUID `0x2A01`)。若未显式调用 API 告知协议栈，该值在 GAP 服务中会为空或默认值，导致主机无法判定其输入设备属性。
* **消解方案**:
  在初始化广播和 GAP 设置后，显式调用 Bluedroid 专有 API 设定本端的 Appearance 图标：
  ```c
  esp_ble_gap_set_device_name(ble_name);
  esp_ble_gap_config_local_icon(0x03C1); // 显式设定本端 GAP 外观为 HID Keyboard
  ```

### 踩坑 2：重连时双向发起加密忙死锁闪断 (BTM_SetEncryption busy)
* **故障现象**: ESP32 重启后，Windows 主动发起重连，串口频繁打印 `BTM_SetEncryption busy` 并立即断开，伴随 Windows 端提示“配对损坏”或连接闪退。
* **原因分析**: Bluedroid 官方 `esp_hid` 的 `ble_hidd.c` 在接收到底层 `ESP_GATTS_CONNECT_EVT` 事件时，会无条件主动调用 `esp_ble_set_encryption()` 发起从端加密。而 Windows 作为主端，重连时也会在几毫秒内主动拉起主端加密。双方同时发起加密在协议栈底层产生锁冲突。
* **先前失败尝试**:
  在 `ble_gatts_config.c` 中通过变量 `s_connect_event_deferred` 拦截已绑定重连的 `GATTS_CONNECT_EVT` 不发给 `esp_hid`，直到 `ESP_GAP_BLE_AUTH_CMPL_EVT` 成功后再补发。
  * **副作用**: 拦截事件导致 Bluedroid 内部的 MTU 交换等基础 GATT/GAP 握手时序不发生，Windows 超时（90ms 左右）直接单方面撕毁连接。
* **最终消解方案**:
  - **恢复直通模式**: 彻底移除对 `GATTS_CONNECT_EVT` 的拦截，保持直通直投。
  - **结合强制关闭休眠与密钥分发**: 运行时调用 `esp_bt_sleep_disable()` 禁用 `Modem Sleep`，保证 RF 射频时钟没有温飘偏置；同时在安全配置里保留双向 `ENC_KEY` 分发声明确保 Windows 成功持久化 Bonding 密钥。此时即使有 `BTM_SetEncryption busy` 提示，协议栈底层能在几百毫秒内自动愈合并成功握手。

### 踩坑 3：重连发生 MIC Failure 闪退 (rsn 0x3d) 并伴随 Device not found
* **故障现象**: ESP32 重启后，Windows 主动发起重连，但在 60ms 内即断连（HCI reason 0x3d / rsn 102），串口显示：
  `W (12131) BT_APPL: bta_dm_ble_smp_cback remove bond,rsn 102, BDA:0xF44EFC143CA7`
  `E (12131) BT_BTM: Device not found`
* **原因分析**:
  配对时本端 `init_key` 仅分发了 `ENC_KEY`，没有分发 `ID_KEY`，导致 Windows 亦未能与本端交换并保存 `IRK` (Identity Resolving Key) 密钥。当 Windows 重启以 RPA (可解析随机地址) 重连时，由于缺乏本端及对端的身份映射，ESP32 判定该设备未曾配对（Device not found），无法获取其 LTK 密钥进行解密，进而触发 MIC Failure 断开。
* **消解方案**:
  在安全参数中将 `init_key` 和 `rsp_key` 设为对称分发模式，允许双方完整交互 `ID_KEY` (IRK 密钥及身份地址)：
  ```c
  uint8_t init_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
  uint8_t rsp_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
  ```

---

## [v2.2-nimble-stable] 纯 NimBLE BLE 键盘稳定里程碑 | 2026-06-19

- **协议栈**: NimBLE (test-bt53-coexist)
- **状态**: 纯 BLE 键盘 (稳定秒连版本)
- **意义**: 成功实现 100% 自动秒连、无重连闪退、闲置不掉线。

### 踩坑 1：冷置几分钟后发生超时断连 (disconnect; reason=546)
* **故障现象**: 键盘不打字静置几分钟后，突然收到 LMP 连接超时错误 (`reason=546`) 自动断开。
* **原因分析**: 蓝牙控制器在闲置时默认开启了 `Modem Sleep` 低功耗休眠，控制器时钟切换到内部 150kHz 的 RC 慢速时钟。由于该时钟精度低且易因温飘产生相位偏移，导致 ESP32 错过了 Windows 发送的 Connection Event 物理时隙，丢包达超时阈值后被强制断连。
* **消解方案**:
  在 `sdkconfig` 中永久禁用 Modem Sleep 选项，并在代码中显式调用：
  ```c
  esp_bt_sleep_disable(); // 强制关闭低功耗休眠，确保射频时钟以满频高精度运行
  ```

### 踩坑 2：重启后自动重连失效与 573 闪退 (MIC Failure)
* **故障现象**: ESP32 重启后，Windows 不发起自动重连；或者重连握手时底层多次报 MIC 校验错误（`reason=573`）后闪断。
* **原因分析**:
  1. **重连失效**: Windows 绑定机制规定，在 Phase 3 密钥分发阶段必须检测到 Encryption Key (`ENC_KEY`)。若出于规避某些冲突的目的把 `ENC_KEY` 强行剥离，Windows 会判定此设备不需要持久 Bonding，断开后直接清除本端配对 LTK，导致重启后无法自动重连。
  2. **MIC Failure**: 主要是休眠温飘丢包引起的解密计数器错位导致的数据校验失败。
* **消解方案**:
  在安全参数中必须保留本端和对端的 `ENC_KEY` 分发声明，允许 Windows 顺利进行持久化 Bonding，结合禁用休眠消除丢包：
  ```c
  ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ```

### 踩坑 3：烧录后无广告广播，卡死在初始化
* **故障现象**: 启动后调试日志卡在 NimBLE 主机启动，电脑搜不到任何蓝牙信号。
* **原因分析**: `esp_hid_gap_init()` 内部初始化会清空并重置全局安全配置 `ble_hs_cfg`。如果我们在其初始化之前挂载了 `sync_cb` 广告启动回调，会被该函数悄悄抹成 `NULL`，导致广告函数从未执行。
* **消解方案**:
  严格调整初始化时序，必须在 `esp_hid_gap_init()` 和 `esp_hid_ble_gap_adv_init()` 调用**之后**，再挂载同步及存储回调：
  ```c
  esp_hid_gap_init(HID_DEV_MODE);
  esp_hid_ble_gap_adv_init(ESP_HID_APPEARANCE_KEYBOARD, dev_name);
  ble_hs_cfg.store_read_cb = my_store_read_cb;
  ble_hs_cfg.sync_cb = nimble_on_sync; // 回调挂载后置，防止被覆盖
  ```
