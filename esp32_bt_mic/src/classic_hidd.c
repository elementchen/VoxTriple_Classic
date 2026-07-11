#include <string.h>
#include "esp_log.h"
#include "esp_hidd_api.h"
#include "classic_hidd.h"
#include "config_storage.h"

static const char *TAG = "CLASSIC_HIDD";
static bool s_hidd_connected = false;

// 经典蓝牙键盘报告描述符 (等同于原 BLE 键盘描述符)
static const uint8_t hid_report_map[] = {
    0x05, 0x01,                    // USAGE_PAGE (Generic Desktop)
    0x09, 0x06,                    // USAGE (Keyboard)
    0xA1, 0x01,                    // COLLECTION (Application)
    0x85, 0x01,                    //   REPORT_ID (1)
    0x05, 0x07,                    //   USAGE_PAGE (Keyboard)
    0x19, 0xE0,                    //   USAGE_MINIMUM (Keyboard LeftControl)
    0x29, 0xE7,                    //   USAGE_MAXIMUM (Keyboard Right GUI)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x01,                    //   LOGICAL_MAXIMUM (1)
    0x75, 0x01,                    //   REPORT_SIZE (1)
    0x95, 0x08,                    //   REPORT_COUNT (8)
    0x81, 0x02,                    //   INPUT (Data,Var,Abs)
    0x95, 0x01,                    //   REPORT_COUNT (1)
    0x75, 0x08,                    //   REPORT_SIZE (8)
    0x81, 0x03,                    //   INPUT (Cnst,Var,Abs)
    0x95, 0x06,                    //   REPORT_COUNT (6)
    0x75, 0x08,                    //   REPORT_SIZE (8)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x65,                    //   LOGICAL_MAXIMUM (101)
    0x05, 0x07,                    //   USAGE_PAGE (Keyboard)
    0x19, 0x00,                    //   USAGE_MINIMUM (Reserved)
    0x29, 0x65,                    //   USAGE_MAXIMUM (Keyboard Application)
    0x81, 0x00,                    //   INPUT (Data,Ary,Abs)
    0xC0                           // END_COLLECTION
};

static void bt_app_hidd_cb(esp_hidd_cb_event_t event, esp_hidd_cb_param_t *param)
{
    switch (event) {
    case ESP_HIDD_EVENT_INIT_MCD:
        ESP_LOGI(TAG, "HID Device Initialized. Registering App...");
        esp_hidd_app_param_t app_param = {
            .name = "ESP32_BT_KBD_MIC",
            .description = "Classic BT Keyboard + Mic",
            .provider = "Espressif",
            .subclass = 0x40, // 键盘 subclass
            .desc_list = (uint8_t *)hid_report_map,
            .desc_list_len = sizeof(hid_report_map)
        };
        esp_bt_hid_device_register_app(&app_param, NULL, NULL);
        break;
    case ESP_HIDD_EVENT_REG_APP:
        ESP_LOGI(TAG, "HID App registered!");
        // 允许被发现和连接
        esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
        break;
    case ESP_HIDD_EVENT_OPEN:
        ESP_LOGI(TAG, "HID host connected: %02X:%02X:%02X:%02X:%02X:%02X",
                 param->open.bd_addr[0], param->open.bd_addr[1],
                 param->open.bd_addr[2], param->open.bd_addr[3],
                 param->open.bd_addr[4], param->open.bd_addr[5]);
        s_hidd_connected = true;
        // 当 Windows 连接成功时，在此自动获取其 MAC 地址并保存，供 PTT 拨接 SCO
        config_storage_save_hfp_addr(param->open.bd_addr);
        break;
    case ESP_HIDD_EVENT_CLOSE:
        ESP_LOGI(TAG, "HID host disconnected");
        s_hidd_connected = false;
        break;
    default:
        break;
    }
}

esp_err_t classic_hidd_init(void)
{
    esp_err_t ret = esp_bt_hid_device_register_callback(bt_app_hidd_cb);
    if (ret != ESP_OK) {
        return ret;
    }
    return esp_bt_hid_device_init();
}

bool classic_hidd_is_connected(void)
{
    return s_hidd_connected;
}

void classic_hidd_send_key(uint8_t modifier, uint8_t key_code)
{
    if (!s_hidd_connected) return;
    uint8_t report[8] = {modifier, 0, key_code, 0, 0, 0, 0, 0};
    esp_bt_hid_device_send_report(ESP_HIDD_REPORT_TYPE_INTRDATA, 1, sizeof(report), report);
}

void classic_hidd_release_key(void)
{
    if (!s_hidd_connected) return;
    uint8_t report[8] = {0};
    esp_bt_hid_device_send_report(ESP_HIDD_REPORT_TYPE_INTRDATA, 1, sizeof(report), report);
}
