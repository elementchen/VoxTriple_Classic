#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_gap_bt_api.h"
#include "esp_hidd_api.h"
#include "esp_hf_client_api.h"
#include "classic_hidd.h"
#include "config_storage.h"

static const char *TAG = "CLASSIC_HIDD";
static bool s_hidd_connected = false;

// 经典蓝牙键盘报告描述符
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

/* Windows VK code -> USB HID Usage ID mapping */
static const uint8_t s_vk_to_hid[256] = {
    [0x08] = 0x2A,  // VK_BACK     -> Backspace
    [0x09] = 0x2B,  // VK_TAB      -> Tab
    [0x0D] = 0x28,  // VK_RETURN   -> Enter
    [0x10] = 0x00,  // VK_SHIFT    -> modifier only
    [0x11] = 0x00,  // VK_CONTROL  -> modifier only
    [0x12] = 0x00,  // VK_MENU     -> modifier only (Alt)
    [0x13] = 0x48,  // VK_PAUSE    -> Pause
    [0x14] = 0x39,  // VK_CAPITAL  -> Caps Lock
    [0x1B] = 0x29,  // VK_ESCAPE   -> Escape
    [0x20] = 0x2C,  // VK_SPACE    -> Spacebar
    [0x21] = 0x4B,  // VK_PRIOR    -> Page Up
    [0x22] = 0x4E,  // VK_NEXT     -> Page Down
    [0x23] = 0x4D,  // VK_END      -> End
    [0x24] = 0x4A,  // VK_HOME     -> Home
    [0x25] = 0x50,  // VK_LEFT     -> Left Arrow
    [0x26] = 0x52,  // VK_UP       -> Up Arrow
    [0x27] = 0x4F,  // VK_RIGHT    -> Right Arrow
    [0x28] = 0x51,  // VK_DOWN     -> Down Arrow
    [0x2C] = 0x46,  // VK_SNAPSHOT -> Print Screen
    [0x2D] = 0x49,  // VK_INSERT   -> Insert
    [0x2E] = 0x4C,  // VK_DELETE   -> Delete Forward
    [0x30] = 0x27,  // 0
    [0x31] = 0x1E,  // 1
    [0x32] = 0x1F,  // 2
    [0x33] = 0x20,  // 3
    [0x34] = 0x21,  // 4
    [0x35] = 0x22,  // 5
    [0x36] = 0x23,  // 6
    [0x37] = 0x24,  // 7
    [0x38] = 0x25,  // 8
    [0x39] = 0x26,  // 9
    [0x41] = 0x04,  // A
    [0x42] = 0x05,  // B
    [0x43] = 0x06,  // C
    [0x44] = 0x07,  // D
    [0x45] = 0x08,  // E
    [0x46] = 0x09,  // F
    [0x47] = 0x0A,  // G
    [0x48] = 0x0B,  // H
    [0x49] = 0x0C,  // I
    [0x4A] = 0x0D,  // J
    [0x4B] = 0x0E,  // K
    [0x4C] = 0x0F,  // L
    [0x4D] = 0x10,  // M
    [0x4E] = 0x11,  // N
    [0x4F] = 0x12,  // O
    [0x50] = 0x13,  // P
    [0x51] = 0x14,  // Q
    [0x52] = 0x15,  // R
    [0x53] = 0x16,  // S
    [0x54] = 0x17,  // T
    [0x55] = 0x18,  // U
    [0x56] = 0x19,  // V
    [0x57] = 0x1A,  // W
    [0x58] = 0x1B,  // X
    [0x59] = 0x1C,  // Y
    [0x5A] = 0x1D,  // Z
    [0x5B] = 0x00,  // VK_LWIN
    [0x5C] = 0x00,  // VK_RWIN
    [0x5D] = 0x65,  // VK_APPS
    [0x60] = 0x62,  // VK_NUMPAD0
    [0x61] = 0x59,  // VK_NUMPAD1
    [0x62] = 0x5A,  // VK_NUMPAD2
    [0x63] = 0x5B,  // VK_NUMPAD3
    [0x64] = 0x5C,  // VK_NUMPAD4
    [0x65] = 0x5D,  // VK_NUMPAD5
    [0x66] = 0x5E,  // VK_NUMPAD6
    [0x67] = 0x5F,  // VK_NUMPAD7
    [0x68] = 0x60,  // VK_NUMPAD8
    [0x69] = 0x61,  // VK_NUMPAD9
    [0x6A] = 0x55,  // VK_MULTIPLY
    [0x6B] = 0x57,  // VK_ADD
    [0x6D] = 0x56,  // VK_SUBTRACT
    [0x6E] = 0x63,  // VK_DECIMAL
    [0x6F] = 0x54,  // VK_DIVIDE
    [0x70] = 0x3A,  // F1
    [0x71] = 0x3B,  // F2
    [0x72] = 0x3C,  // F3
    [0x73] = 0x3D,  // F4
    [0x74] = 0x3E,  // F5
    [0x75] = 0x3F,  // F6
    [0x76] = 0x40,  // F7
    [0x77] = 0x41,  // F8
    [0x78] = 0x42,  // F9
    [0x79] = 0x43,  // F10
    [0x7A] = 0x44,  // F11
    [0x7B] = 0x45,  // F12
    [0x90] = 0x53,  // VK_NUMLOCK
    [0xA0] = 0x00,  // VK_LSHIFT
    [0xA1] = 0x00,  // VK_RSHIFT
    [0xA2] = 0x00,  // VK_LCONTROL
    [0xA3] = 0x00,  // VK_RCONTROL
    [0xA4] = 0x00,  // VK_LMENU
    [0xA5] = 0x00,  // VK_RMENU
    [0xAD] = 0xE2,  // VK_VOLUME_MUTE
    [0xAE] = 0xEA,  // VK_VOLUME_DOWN
    [0xAF] = 0xE9,  // VK_VOLUME_UP
    [0xB0] = 0xB6,  // VK_MEDIA_NEXT_TRACK
    [0xB1] = 0xB5,  // VK_MEDIA_PREV_TRACK
    [0xB3] = 0xCD,  // VK_MEDIA_PLAY_PAUSE
    [0xBA] = 0x33,  // VK_OEM_1
    [0xBB] = 0x2E,  // VK_OEM_PLUS
    [0xBC] = 0x36,  // VK_OEM_COMMA
    [0xBD] = 0x2D,  // VK_OEM_MINUS
    [0xBE] = 0x37,  // VK_OEM_PERIOD
    [0xBF] = 0x38,  // VK_OEM_2
    [0xC0] = 0x35,  // VK_OEM_3
    [0xDB] = 0x2F,  // VK_OEM_4
    [0xDC] = 0x31,  // VK_OEM_5
    [0xDD] = 0x30,  // VK_OEM_6
    [0xDE] = 0x34,  // VK_OEM_7
};

static uint8_t vk_to_hid_modifier(uint8_t vk)
{
    switch (vk) {
    case 0xA2: return 0x01;  // VK_LCONTROL
    case 0xA3: return 0x10;  // VK_RCONTROL
    case 0xA0: return 0x02;  // VK_LSHIFT
    case 0xA1: return 0x20;  // VK_RSHIFT
    case 0xA4: return 0x04;  // VK_LMENU (Left Alt)
    case 0xA5: return 0x40;  // VK_RMENU (Right Alt)
    case 0x5B: return 0x08;  // VK_LWIN
    case 0x5C: return 0x80;  // VK_RWIN
    case 0x10: return 0x02;  // VK_SHIFT   -> left shift
    case 0x11: return 0x01;  // VK_CONTROL -> left control
    case 0x12: return 0x04;  // VK_MENU    -> left alt
    default:   return 0x00;
    }
}

static inline uint8_t vk_mod_to_hid(uint8_t mod_mask)
{
    uint8_t hid_mod = 0;
    if (mod_mask & 0x01) hid_mod |= 0x01;  // LCtrl
    if (mod_mask & 0x02) hid_mod |= 0x02;  // LShift
    if (mod_mask & 0x04) hid_mod |= 0x04;  // LAlt
    if (mod_mask & 0x08) hid_mod |= 0x08;  // LGUI
    if (mod_mask & 0x10) hid_mod |= 0x10;  // RCtrl
    if (mod_mask & 0x20) hid_mod |= 0x20;  // RShift
    if (mod_mask & 0x40) hid_mod |= 0x40;  // RAlt
    if (mod_mask & 0x80) hid_mod |= 0x80;  // RGUI
    return hid_mod;
}

static void bt_app_hidd_cb(esp_hidd_cb_event_t event, esp_hidd_cb_param_t *param)
{
    switch (event) {
    case ESP_HIDD_INIT_EVT:
        ESP_LOGI(TAG, "HID Device Initialized. Registering App...");
        
        /* Bluedroid btc_hd.c utilizes strict memcpy(..., BTC_HD_APP_xxx_LEN) which defaults to 50 bytes.
         * We MUST provide 50-byte padded buffers to prevent fatal out-of-bounds read Page Fault crashes. */
        static char name_buf[50] = {0};
        static char desc_buf[50] = {0};
        static char prov_buf[50] = {0};
        
        memset(name_buf, 0, sizeof(name_buf));
        memset(desc_buf, 0, sizeof(desc_buf));
        memset(prov_buf, 0, sizeof(prov_buf));
        
        strncpy(name_buf, "ESP32_BT_KBD_MIC", sizeof(name_buf) - 1);
        strncpy(desc_buf, "Classic BT Keyboard + Mic", sizeof(desc_buf) - 1);
        strncpy(prov_buf, "Espressif", sizeof(prov_buf) - 1);

        /* All parameters passed to esp_bt_hid_device_register_app MUST be static/global.
         * The Bluedroid API processes this request asynchronously in the BTC_TASK thread.
         * If they are stack-allocated, they will be reclaimed before BTC_TASK runs, leading to fatal wild pointer LoadProhibited crashes. */
        static esp_hidd_app_param_t app_param;
        app_param.name = name_buf;
        app_param.description = desc_buf;
        app_param.provider = prov_buf;
        app_param.subclass = 0x40; // Keyboard subclass
        app_param.desc_list = (uint8_t *)hid_report_map;
        app_param.desc_list_len = sizeof(hid_report_map);

        static esp_hidd_qos_param_t in_qos = {
            .service_type = 1, // Best Effort
            .token_rate = 0,
            .token_bucket_size = 0,
            .peak_bandwidth = 0,
            .access_latency = 0,
            .delay_variation = 0
        };
        static esp_hidd_qos_param_t out_qos = {
            .service_type = 1,
            .token_rate = 0,
            .token_bucket_size = 0,
            .peak_bandwidth = 0,
            .access_latency = 0,
            .delay_variation = 0
        };

        esp_bt_hid_device_register_app(&app_param, &in_qos, &out_qos);
        break;
    case ESP_HIDD_REGISTER_APP_EVT:
        ESP_LOGI(TAG, "HID App registered!");
        // 允许被发现和连接
        esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
        
        // 主动连接上一次配对保存 of Windows 电脑，实现重启秒连
        esp_bd_addr_t saved_addr = {0};
        if (config_storage_load_hfp_addr(saved_addr) == ESP_OK) {
            ESP_LOGI(TAG, "Saved host address found. Initiating auto-reconnect to Host...");
            esp_bt_hid_device_connect(saved_addr);
            esp_hf_client_connect(saved_addr); // 开机自动把 HFP 麦克风信道一并连接
        } else {
            ESP_LOGI(TAG, "No saved host address. Waiting for initial pairing...");
        }
        break;
    case ESP_HIDD_OPEN_EVT:
        ESP_LOGI(TAG, "HID Open Event: status=%d, conn_status=%d", param->open.status, param->open.conn_status);
        if (param->open.status == ESP_HIDD_SUCCESS && param->open.conn_status == ESP_HIDD_CONN_STATE_CONNECTED) {
            ESP_LOGI(TAG, "HID host connected: %02X:%02X:%02X:%02X:%02X:%02X",
                     param->open.bd_addr[0], param->open.bd_addr[1],
                     param->open.bd_addr[2], param->open.bd_addr[3],
                     param->open.bd_addr[4], param->open.bd_addr[5]);
            s_hidd_connected = true;
            // 当 Windows 连接成功时，在此自动获取其 MAC 地址并保存，供 PTT 拨接 SCO
            config_storage_save_hfp_addr(param->open.bd_addr);

            // 联动连接：HID 键盘连接成功后，在后台确保 HFP 麦克风控制链路一并打通
            extern bool bt_hfp_is_connected(void);
            if (!bt_hfp_is_connected()) {
                ESP_LOGI(TAG, "HID channel opened. Initiating backup HFP client connection...");
                esp_hf_client_connect(param->open.bd_addr);
            }
        } else {
            ESP_LOGW(TAG, "HID connection in progress or failed. Key inputs disabled.");
            s_hidd_connected = false;
        }
        break;
    case ESP_HIDD_CLOSE_EVT:
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
    
    uint8_t hid_mod = vk_mod_to_hid(modifier);
    hid_mod |= vk_to_hid_modifier(key_code);
    uint8_t hid_key = s_vk_to_hid[key_code];
    
    // Send Key Press report only, do not auto-release here
    uint8_t report[8] = {hid_mod, 0, hid_key, 0, 0, 0, 0, 0};
    esp_bt_hid_device_send_report(ESP_HIDD_REPORT_TYPE_INTRDATA, 1, sizeof(report), report);
}

void classic_hidd_release_key(void)
{
    if (!s_hidd_connected) return;
    uint8_t report[8] = {0};
    esp_bt_hid_device_send_report(ESP_HIDD_REPORT_TYPE_INTRDATA, 1, sizeof(report), report);
}
