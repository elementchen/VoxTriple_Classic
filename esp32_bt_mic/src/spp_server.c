#include <stdint.h>
#include <string.h>
#include "esp_log.h"
#include "esp_spp_api.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_bt_api.h"
#include "config_cmd.h"
#include "spp_server.h"

#define TAG "SPP_SERVER"
#define SPP_SERVER_NAME "VoxTriple_SPP"

static uint32_t s_spp_conn_handle = 0;
static bool s_spp_connected = false;

#define SPP_RX_BUF_SIZE  512
static char s_rx_buf[SPP_RX_BUF_SIZE];
static size_t s_rx_len = 0;

static void spp_respond_cb(const char *data, size_t len)
{
    esp_spp_write(s_spp_conn_handle, len, (uint8_t *)data);
}

static void handle_spp_data(const uint8_t *data, size_t len)
{
    if (s_rx_len + len >= SPP_RX_BUF_SIZE) {
        ESP_LOGW(TAG, "RX buffer overflow, clearing");
        s_rx_len = 0;
    }
    
    memcpy(s_rx_buf + s_rx_len, data, len);
    s_rx_len += len;
    s_rx_buf[s_rx_len] = '\0';
    
    char *line_start = s_rx_buf;
    char *line_end;
    while ((line_end = strchr(line_start, '\n')) != NULL) {
        *line_end = '\0';
        char *r_char = strchr(line_start, '\r');
        if (r_char) *r_char = '\0';
        
        if (strlen(line_start) > 0) {
            execute_config_cmd(line_start, strlen(line_start), spp_respond_cb);
        }
        
        line_start = line_end + 1;
    }
    
    size_t processed_len = line_start - s_rx_buf;
    if (processed_len > 0) {
        if (processed_len < s_rx_len) {
            memmove(s_rx_buf, line_start, s_rx_len - processed_len);
            s_rx_len -= processed_len;
        } else {
            s_rx_len = 0;
        }
    }
}

static void spp_cb(esp_spp_cb_event_t event, esp_spp_cb_param_t *param)
{
    switch (event) {
    case ESP_SPP_INIT_EVT:
        ESP_LOGI(TAG, "SPP Initialized. Starting server...");
        esp_spp_start_srv(ESP_SPP_SEC_NONE, ESP_SPP_ROLE_SLAVE, 0, SPP_SERVER_NAME);
        break;
    case ESP_SPP_START_EVT:
        ESP_LOGI(TAG, "SPP Server started");
        break;
    case ESP_SPP_SRV_OPEN_EVT:
        ESP_LOGI(TAG, "SPP Connection opened: handle=%lu, address=%02X:%02X:%02X:%02X:%02X:%02X",
                 param->srv_open.handle,
                 param->srv_open.rem_bda[0], param->srv_open.rem_bda[1],
                 param->srv_open.rem_bda[2], param->srv_open.rem_bda[3],
                 param->srv_open.rem_bda[4], param->srv_open.rem_bda[5]);
        s_spp_conn_handle = param->srv_open.handle;
        s_spp_connected = true;
        s_rx_len = 0;
        break;
    case ESP_SPP_CLOSE_EVT:
        ESP_LOGI(TAG, "SPP Connection closed: handle=%lu", param->close.handle);
        s_spp_connected = false;
        s_spp_conn_handle = 0;
        break;
    case ESP_SPP_DATA_IND_EVT:
        handle_spp_data(param->data_ind.data, param->data_ind.len);
        break;
    default:
        break;
    }
}

esp_err_t spp_server_init(void)
{
    esp_err_t ret = esp_spp_register_callback(spp_cb);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "spp register cb failed: %s", esp_err_to_name(ret));
        return ret;
    }
    ret = esp_spp_init(ESP_SPP_MODE_CB);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "spp init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    return ESP_OK;
}

void spp_server_send_event_btn(uint8_t btn_id, uint8_t state)
{
    if (s_spp_connected) {
        char resp[64];
        snprintf(resp, sizeof(resp), "{\"event\":\"btn\",\"id\":%d,\"state\":%d}\n", btn_id, state);
        esp_spp_write(s_spp_conn_handle, strlen(resp), (uint8_t *)resp);
    }
}

void spp_server_send_event_status(uint8_t hfp_connected, uint8_t audio_active)
{
    if (s_spp_connected) {
        char resp[64];
        snprintf(resp, sizeof(resp), "{\"event\":\"status\",\"hfp\":%d,\"audio\":%d}\n", hfp_connected, audio_active);
        esp_spp_write(s_spp_conn_handle, strlen(resp), (uint8_t *)resp);
    }
}
