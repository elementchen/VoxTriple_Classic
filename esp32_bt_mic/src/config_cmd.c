#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "esp_bt.h"
#include "cJSON.h"
#include "config_storage.h"
#include "config_cmd.h"
#include "uart_console.h"
#include "esp_app_desc.h"

#define TAG "CONFIG_CMD"

void execute_config_cmd(const char *cmd_line, size_t len, cmd_respond_cb_t respond_cb)
{
    if (!respond_cb) {
        return;
    }

    cJSON *root = cJSON_ParseWithLength(cmd_line, len);
    if (!root) {
        ESP_LOGE(TAG, "JSON Parse failed: %.*s", (int)len, cmd_line);
        return;
    }
    
    cJSON *cmd_item = cJSON_GetObjectItem(root, "cmd");
    if (cmd_item && cJSON_IsString(cmd_item)) {
        const char *cmd = cmd_item->valuestring;
        
        if (strcmp(cmd, "get_config") == 0) {
            uint8_t vk1, mod1, vk2, mod2, vk3, mod3, vk4, mod4;
            config_storage_load_button(0, &vk1, &mod1);
            config_storage_load_button(1, &vk2, &mod2);
            config_storage_load_button(2, &vk3, &mod3);
            config_storage_load_button(3, &vk4, &mod4);
            
            uint8_t tx_power = 7;
            config_storage_load_tx_power(&tx_power);
            uint8_t sleep_mode = 0;
            config_storage_load_sleep_mode(&sleep_mode);
            
            const esp_app_desc_t *app_desc = esp_app_get_description();
            char resp[320];
            snprintf(resp, sizeof(resp), 
                     "{\"status\":\"ok\",\"version\":\"%s\",\"btn1_vk\":%d,\"btn1_mod\":%d,\"btn2_vk\":%d,\"btn2_mod\":%d,"
                     "\"btn3_vk\":%d,\"btn3_mod\":%d,\"btn4_vk\":%d,\"btn4_mod\":%d,\"tx_power\":%d,\"sleep_mode\":%d}\n",
                     app_desc->version, vk1, mod1, vk2, mod2, vk3, mod3, vk4, mod4, tx_power, sleep_mode);
            respond_cb(resp, strlen(resp));
            
        } else if (strcmp(cmd, "set_btn") == 0) {
            cJSON *idx_item = cJSON_GetObjectItem(root, "idx");
            cJSON *vk_item = cJSON_GetObjectItem(root, "vk");
            cJSON *mod_item = cJSON_GetObjectItem(root, "mod");
            if (idx_item && vk_item && mod_item && cJSON_IsNumber(idx_item) && cJSON_IsNumber(vk_item) && cJSON_IsNumber(mod_item)) {
                uint8_t idx = idx_item->valueint;
                uint8_t vk = vk_item->valueint;
                uint8_t mod = mod_item->valueint;
                config_storage_save_button(idx, vk, mod);
                
                const char *resp = "{\"status\":\"ok\"}\n";
                respond_cb(resp, strlen(resp));
            }
            
        } else if (strcmp(cmd, "set_tx_power") == 0) {
            cJSON *level_item = cJSON_GetObjectItem(root, "level");
            if (level_item && cJSON_IsNumber(level_item)) {
                uint8_t level = level_item->valueint;
                config_storage_save_tx_power(level);
                esp_bredr_tx_power_set((esp_power_level_t)level, (esp_power_level_t)level);
                
                const char *resp = "{\"status\":\"ok\"}\n";
                respond_cb(resp, strlen(resp));
            }
            
        } else if (strcmp(cmd, "set_sleep_mode") == 0) {
            cJSON *enabled_item = cJSON_GetObjectItem(root, "enabled");
            if (enabled_item && cJSON_IsNumber(enabled_item)) {
                uint8_t enabled = enabled_item->valueint;
                config_storage_save_sleep_mode(enabled);
                
                const char *resp = "{\"status\":\"ok\"}\n";
                respond_cb(resp, strlen(resp));
            }
        } else if (strcmp(cmd, "ota_start") == 0) {
            cJSON *size_item = cJSON_GetObjectItem(root, "size");
            if (size_item && cJSON_IsNumber(size_item)) {
                size_t ota_size = size_item->valueint;
                esp_err_t err = uart_console_ota_start(ota_size);
                if (err == ESP_OK) {
                    const char *resp = "{\"status\":\"ok\"}\n";
                    respond_cb(resp, strlen(resp));
                } else {
                    char resp[128];
                    snprintf(resp, sizeof(resp), "{\"status\":\"error\",\"reason\":\"ota_begin_failed: %d\"}\n", err);
                    respond_cb(resp, strlen(resp));
                }
            }
        }
    }
    cJSON_Delete(root);
}
