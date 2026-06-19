#ifndef BT_CONFIG_H
#define BT_CONFIG_H

/* 逐步诊断经典蓝牙干扰 BLE 键盘自动重连的宏开关
 * 0: 完全禁用经典蓝牙（纯 BLE 键盘模式进行验证）
 * 1: 启用经典蓝牙耳麦与双模共存
 */
#define ENABLE_CLASSIC_BT_MIC 0

#endif // BT_CONFIG_H
