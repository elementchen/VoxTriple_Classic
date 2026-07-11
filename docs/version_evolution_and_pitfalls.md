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
* **原因分析**: Bluedroid 官方 `esp_hid` 的 `ble_hidd.c` 在接收到底层 `ESP_GATTS_CONNECT_EVT` 事件时，会无条件主动调用 `esp_ble_set_encryption()` 发起从端加密（Security Request）。而 Windows 作为主端，重连时也会在几毫秒内主动拉起主端加密（`LL_ENC_REQ`）。两端并发发起加密在协议栈底层产生锁冲突。
* **先前失败尝试**：
  1. 通过变量拦截 `GATTS_CONNECT_EVT` 导致 Windows 超时。
  2. 采用 GCC wrapper 将 `esp_ble_set_encryption` 延迟 500ms 触发。但在延迟的 500ms 期间，Windows 仍会在 40ms 时发起加密并与后续的 500ms 延时调用发生时序冲突，且仍存双向碰撞隐患。
* **最终消解方案 (被动响应加密拦截)**:
  在 GCC Wrapper (`__wrap_esp_ble_set_encryption`) 中，对已绑定重连的设备（`bond_num > 0`），直接丢弃主动加密请求并返回 `ESP_OK`（彻底不调用 `__real_esp_ble_set_encryption`）。这样从端绝对不会主动拉起加密，而是 100% 被动响应主端 Windows 的加密包，时序最简，彻底消除了碰撞和锁死。

### 踩坑 3：重连发生 MIC Failure 闪退 (rsn 0x3d) 并伴随 Device not found
* **故障现象**: ESP32 重启后，Windows 主动发起重连，但在 40ms 内即断连（HCI reason 0x3d / rsn 102），串口显示 `bta_dm_ble_smp_cback remove bond,rsn 102` 并删除绑定。
* **原因分析**:
  先前尝试在安全参数中将 `init_key` 和 `rsp_key` 仅设为分发 `ID_KEY`（剥离了 `ENC_KEY`），希望防止 NVS 写入 `LE_KEY_PENC`。但这导致 Windows 蓝牙子系统没有保存或正确同步 LTK。重连时，Windows 发起加密，而 ESP32 响应的密钥不匹配，导致控制器发生 MIC Failure。
* **最终消解方案 (对称分发还原)**:
  必须在 GAP 初始化时，将 `init_key` 和 `rsp_key` 还原为对称包含 `ENC_KEY` 和 `ID_KEY`，确保配对时两端均成功且完整同步 LTK 和 IRK 信息：
  ```c
  uint8_t init_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
  uint8_t rsp_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
  ```
  结合被动加密拦截，Windows 在重连时发送加密请求，ESP32 纯被动使用加载的 LTK 顺利完成解密，不再发生 MIC Failure 闪退。

### 踩坑 4：纯 BLE 控制器模式下重连 `key_mask` 畸变为 `0x6B` 并导致 MIC Failure (0x3d)
* **故障现象**: 在限制为纯 BLE 控制器模式且擦除 NVS 重新烧录后，首次配对成功时 `key_mask` 打印为 `0x67`。但按 EN 重启设备后，系统从 NVS 加载设备列表时，`key_mask` 却畸变为了 `0x6B`（即多出了 `ESP_LE_KEY_PLNK` 0x08 标志并丢失了 `PCSRK` 0x04 签名标志），自动重连时依然会由于解密错误触发 `0x3d` (MIC Failure) 断连。
* **原因分析**:
  这是因为在广播参数配置中，仅设置了 `ESP_BLE_ADV_FLAG_GEN_DISC`，**缺省了代表不支持经典蓝牙的 `ESP_BLE_ADV_FLAG_BREDR_NOT_SPT` (0x04) 标志**。对端 Windows 收到广播后判定该设备支持经典蓝牙（BR/EDR），于是在配对阶段自动拉起了跨传输密钥派生 (CTKD)，在后台派生并写入了经典蓝牙的 `Link Key` 并存入 NVS。
  重启加载设备时，Bluedroid 从 NVS 中读取到该设备的 Link Key 记录，自动将设备识别为双模类型并将 `key_mask` 改为包含 `PLNK` (0x6B)。这种与纯 BLE 模式（Classic BT 控制器内存已完全释放）的不一致，导致了重连时协议栈解析与加载 LTK 错位，进而引发解密 MIC Failure。
* **消解方案 (编译开启控制器 RPA 硬件解析与启用本地隐私)**:
  通过开启编译期底层 RPA 解析并调用 GAP API 注册 IRK，从根本上解决 RPA 重连识别延迟的问题：
  1. **启用编译配置**：在 `sdkconfig.nodemcu-32s` 和 `sdkconfig.defaults` 中，显式将 `# CONFIG_BT_BLE_RPA_SUPPORTED is not set` 变更为 **`CONFIG_BT_BLE_RPA_SUPPORTED=y`**。
  2. **在广播中启用本地隐私 (Privacy)**：在 `ble_gatts_config.c` 的 `ble_init_adv_data` 阶段，在配置好安全参数后，显式调用 **`esp_ble_gap_config_local_privacy(true)`**：
     ```c
     esp_ble_gap_config_local_privacy(true);
     ```
     这会使 Bluedroid 协议栈在初始化时，自动将 NVS 中加载的已配对设备的 Identity Resolving Key (IRK) 注册写入控制器的硬件 Resolving List 中。
  3. **保留 SC 配对级别**：有了底层的 RPA 硬件解析与广播 flags 的 `BREDR_NOT_SPT` 保护，本端可以继续使用高安全性的 **Secure Connections (`ESP_LE_AUTH_REQ_SC_BOND`)** 模式，实现安全的加密连接。
  
  通过此方案，重启后 Windows 发起加密时，控制器能够在硬件层面瞬间将 RPA 地址解析为 Identity Address (`F4:4E:FC:14:3C:A7`) 并正确加载对应的 LTK 配合解密，彻底消除 `Device not found` 与 `MIC Failure (0x3d)` 闪退，达到 100% 极速重连。

### 踩坑 5：从端直接屏蔽 `esp_ble_set_encryption` 导致 BTM 安全上下文缺失
* **故障现象**: 重连时依然发生 `remove bond, rsn 102` 与 `Device not found` 错误，连接瞬间断连。
* **原因分析**: 
  之前版本中，为了防止双向并发加密冲突，我们在 GCC Wrapper 中直接对 `bond_num > 0` 的连接返回了 `ESP_OK`（完全屏蔽了底层 `esp_ble_set_encryption` 的执行）。
  然而，完全屏蔽该调用导致 Bluedroid 的 BTM (Bluetooth Manager) 安全管理模块未能为当前 `conn_id` 初始化与绑定有效的安全操作上下文。因此，当主端 Windows 发起 `LL_ENC_REQ` 加密请求时，ESP32 侧底层触发了 `BT_BTM: Device not found` 导致解密失败（MIC Failure / 0x3d），并将该失败归咎于 SMP 握手超时（rsn 102），从而在 flash 中自动删除了绑定。
* **最终消解方案 (延迟 10 秒放行安全上下文)**:
  不能彻底屏蔽 `esp_ble_set_encryption`，而是需要延迟调用它。
  在 Wrapper 中，对于重连设备，我们使用一个 **10秒延时定时器** 延迟执行真实的 `__real_esp_ble_set_encryption`。
  1. **给 Windows 充足时间**：这确保了连接建立后的前几秒内，从端绝对不会主动发送 Security Request。Windows 有充足时间主动发起主端加密并完成 LTK 握手。
  2. **保留安全上下文初始化**：10秒后定时器触发，调用真实接口，使得 BTM 安全上下文得以在协议栈内部安全地更新/关联。由于此时链路通常早已加密完成，底层会安全忽略该冗余请求而不发起空中冲突。
  3. **断连安全保护**：若在 10 秒内设备意外断连，则自动取消该定时器，防止野定时器触发崩溃。

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

---

## [v2.4-dual-mode-reconnect-fix] 双模安全重连验证版本 | 2026-06-19

- **协议栈**: Bluedroid
- **状态**: 经典 HFP + BLE 键盘双模共存，并且本端配置双 MAC（HFP使用物理 MAC，BLE使用静态随机 MAC）。
- **目的**: 解决 Windows 侧对端 MAC 重叠引起的 NVS 绑定覆盖冲突，以实现稳定的双模自动回连。

### 踩坑 1：回退至 Legacy Pairing 禁用 CTKD 后，LTK 仍被抹去 (key_mask 变 0x16)
* **故障现象**: 在 Legacy Pairing 模式（`auth_req = ESP_LE_AUTH_BOND`）下，首次配对成功时 `key_mask = 0x63`。但 EN 重启设备后，`key_mask` 仍退化为 `0x16`，丢失了 `0x01`（`ESP_LE_KEY_PENC` 对端加密密钥 LTK），从而再次在连接瞬间因 `Device not found` 而导致 `rsn 0x3d` (MIC Failure) 删绑。
* **原因分析**: 
  即使我们成功关闭了 CTKD（没有派生 Link Key 和 LTK 互导），但是由于 Windows（对端）无论连接经典蓝牙还是连接 BLE 键盘，其发起连接的物理 MAC 均为相同的 `F4:4E:FC:14:3C:A7`。
  在 Bluedroid 的内部 NVS 加载中，它读取的是全局配置文件下以对端 MAC 作为键的设备记录。由于这台设备同时注册了经典蓝牙 Link Key 与 BLE 配对项，Bluedroid 在反序列化加载时，依然发生了解析冲突，强行忽略或丢弃了 BLE 的对端 LTK。
* **下一步探索方向**:
  我们需要在经典蓝牙侧寻找避坑方案。如果经典蓝牙可以配置为“免配对保存”（在与 Windows 连接时仅使用临时 Security Key 而不在本端持久保存 Link Key），则 NVS 中将永远只有干净的 BLE `PENC`（LTK）记录，这也许是唯一既能保障双模又能保护 BLE 重连不被擦除的有效方法。

