/*
 * SPDX-FileCopyrightText: 2024 ESP32 BT Microphone Project
 *
 * SPDX-License-Identifier: Unlicense OR CC0-1.0
 */

#include "board_profile.h"
#include "config_storage.h"
#include "esp_log.h"

static const char *TAG = "BOARD_PROFILE";

static const board_profile_t s_board_profiles[BOARD_MODEL_MAX] = {
    [BOARD_MODEL_WEMOS_18650] = {
        .model = BOARD_MODEL_WEMOS_18650,
        .model_name = "WEMOS 18650",
        .led_gpio = GPIO_NUM_16,
        .i2s_bck_gpio = GPIO_NUM_21,
        .i2s_ws_gpio = GPIO_NUM_22,
        .i2s_data_gpio = GPIO_NUM_17,
        .btn_gpios = { GPIO_NUM_4, GPIO_NUM_18, GPIO_NUM_19, GPIO_NUM_23 }
    },
    [BOARD_MODEL_ESP32_LITE_V1] = {
        .model = BOARD_MODEL_ESP32_LITE_V1,
        .model_name = "ESP32 Lite V1.0.0",
        .led_gpio = GPIO_NUM_22,
        .i2s_bck_gpio = GPIO_NUM_27,
        .i2s_ws_gpio = GPIO_NUM_26,
        .i2s_data_gpio = GPIO_NUM_25,
        .btn_gpios = { GPIO_NUM_4, GPIO_NUM_19, GPIO_NUM_23, GPIO_NUM_18 }
    }
};

static board_model_t s_current_model = BOARD_MODEL_ESP32_LITE_V1;

void board_profile_init(void)
{
    uint8_t model = 0;
    esp_err_t err = config_storage_load_board_model(&model);
    if (err == ESP_OK && model < BOARD_MODEL_MAX) {
        s_current_model = (board_model_t)model;
    } else {
        s_current_model = BOARD_MODEL_ESP32_LITE_V1;
    }
    ESP_LOGI(TAG, "Active Board Profile: [%d] %s (LED=%d, BCK=%d, WS=%d, DATA=%d)",
             s_current_model, s_board_profiles[s_current_model].model_name,
             s_board_profiles[s_current_model].led_gpio,
             s_board_profiles[s_current_model].i2s_bck_gpio,
             s_board_profiles[s_current_model].i2s_ws_gpio,
             s_board_profiles[s_current_model].i2s_data_gpio);
}

const board_profile_t *board_profile_get_current(void)
{
    return &s_board_profiles[s_current_model];
}

esp_err_t board_profile_set_model(board_model_t model)
{
    if (model >= BOARD_MODEL_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    s_current_model = model;
    return config_storage_save_board_model((uint8_t)model);
}
