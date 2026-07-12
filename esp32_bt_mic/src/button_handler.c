/*
 * SPDX-FileCopyrightText: 2024 ESP32 BT Microphone Project
 *
 * SPDX-License-Identifier: Unlicense OR CC0-1.0
 */

#include <stdint.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "esp_gap_bt_api.h"
#include "esp_hidd_api.h"
#include "button_handler.h"
#include "classic_hidd.h"
#include "config_storage.h"
#include "bt_init.h"
#include "esp_hf_client_api.h"
#include "uart_console.h"
#include "bt_config.h"

static const char *TAG = "BTN_HANDLER";

/* Button GPIO configuration */
#define DEBOUNCE_MS          50
#define LONG_PRESS_MS        1000
#define BUTTON_TASK_STACK    4096
#define BUTTON_TASK_PRIORITY 3

#define INDICATOR_LED_GPIO   GPIO_NUM_18
#define INACTIVITY_MS        (30 * 60 * 1000)  /* 30 min deep sleep timeout */

static TimerHandle_t s_inactivity_timer = NULL;

/* Enter deep sleep — power down WiFi/BT/CPU. GPIO4 (RTC) will wake us. */
static void inactivity_sleep_cb(TimerHandle_t xTimer)
{
    ESP_LOGI(TAG, "30 min idle — entering deep sleep (press any key to wake)");

    /* Keep GPIO4 pull-up during deep sleep so button press pulls it LOW */
    rtc_gpio_pullup_en(GPIO_NUM_4);
    rtc_gpio_pulldown_dis(GPIO_NUM_4);
    esp_sleep_enable_ext1_wakeup(1ULL << GPIO_NUM_4, ESP_EXT1_WAKEUP_ALL_LOW);

    vTaskDelay(pdMS_TO_TICKS(100));  /* let log flush */
    esp_deep_sleep_start();
}

static void get_button_mapping(uint8_t button_id, uint8_t *vk_code, uint8_t *modifier)
{
    if (config_storage_load_button(button_id, vk_code, modifier) != ESP_OK) {
        *modifier = 0;
        if (button_id == 0) *vk_code = 0x0D; // Enter
        else if (button_id == 1) *vk_code = 0x1B; // Esc
        else if (button_id == 2) *vk_code = 0x20; // Space
        else if (button_id == 3) *vk_code = 0x09; // Tab
    }
}

static const gpio_num_t s_button_pins[BUTTON_NUM] = {
    CONFIG_BUTTON_1_GPIO,
    CONFIG_BUTTON_2_GPIO,
    CONFIG_BUTTON_3_GPIO,
    CONFIG_BUTTON_4_GPIO,
};

typedef enum {
    BTN_STATE_IDLE,
    BTN_STATE_DEBOUNCE,
    BTN_STATE_PRESSED,
} btn_state_t;

static TaskHandle_t s_btn_task_handle = NULL;
static bool s_btn_task_running = false;

/**
 * @brief Button monitoring task with debounce
 */
static void button_task_func(void *arg)
{
    btn_state_t state[BUTTON_NUM];
    uint32_t press_time[BUTTON_NUM];
    uint32_t last_change[BUTTON_NUM];
    uint32_t now;

    memset(state, 0, sizeof(state));
    memset(press_time, 0, sizeof(press_time));
    memset(last_change, 0, sizeof(last_change));

    ESP_LOGI(TAG, "Button task started (GPIOs: %d, %d, %d, %d)",
             s_button_pins[0], s_button_pins[1], s_button_pins[2], s_button_pins[3]);

    while (s_btn_task_running) {
        now = xTaskGetTickCount() * portTICK_PERIOD_MS;

        for (int i = 0; i < BUTTON_NUM; i++) {
            int level = gpio_get_level(s_button_pins[i]);
            int pressed = (level == 0);  /* Active low: pressed = low */

            switch (state[i]) {
            case BTN_STATE_IDLE:
                if (pressed) {
                    state[i] = BTN_STATE_DEBOUNCE;
                    last_change[i] = now;
                }
                break;

            case BTN_STATE_DEBOUNCE:
                if (!pressed) {
                    state[i] = BTN_STATE_IDLE;
                } else if ((now - last_change[i]) >= DEBOUNCE_MS) {
                    state[i] = BTN_STATE_PRESSED;
                    press_time[i] = now;
                    ESP_LOGI(TAG, "Button %d pressed", i + 1);
                    uart_console_send_event_btn(i, 1); // Notify PC over UART

                    /* Reset inactivity deep sleep timer */
                    if (s_inactivity_timer) xTimerReset(s_inactivity_timer, 0);

                    /* Connection wake-up: if BLE is not connected, trigger advertising to connect keyboard.
                     * If BLE is already connected, activate Classic BT HFP (on key press) to connect microphone. */
                    /* Connection wake-up & HFP SCO activation */
                    if (classic_hidd_is_connected()) {
                        uint8_t vk = 0, mod = 0;
                        get_button_mapping(i, &vk, &mod);
                        classic_hidd_send_key(mod, vk);
                    } else {
                        ESP_LOGW(TAG, "Classic BT HID not connected. Button press triggers reconnect...");
                        esp_bd_addr_t saved_addr;
                        if (config_storage_load_hfp_addr(saved_addr) == ESP_OK) {
                            ESP_LOGI(TAG, "Saved host address found. Initiating reconnect to Host...");
                            esp_bt_hid_device_connect(saved_addr);
                        }
                    }
                }
                break;

            case BTN_STATE_PRESSED:
                if (!pressed) {
                    uint32_t duration = now - press_time[i];
                    ESP_LOGI(TAG, "Button %d released (duration: %lu ms)", i + 1, duration);
                    uart_console_send_event_btn(i, 0); // Notify PC over UART
                    if (classic_hidd_is_connected()) {
                        classic_hidd_release_key();
                    }

                    /* Button 4 long press (> 3000ms) to clear all BT pairings & reset */
                    if (i == 3 && duration >= 3000) {
                        ESP_LOGW(TAG, "Button 4 long pressed! Clearing BT pairings and restarting...");
                        
                        // 1. Flash LED as physical feedback
                        for (int j = 0; j < 6; j++) {
                            gpio_set_level(INDICATOR_LED_GPIO, j % 2);
                            vTaskDelay(pdMS_TO_TICKS(100));
                        }
                        
                        // 2. Remove pairing bond info from Bluedroid stack
                        esp_bd_addr_t saved_addr;
                        if (config_storage_load_hfp_addr(saved_addr) == ESP_OK) {
                            esp_bt_gap_remove_bond_device(saved_addr);
                        }
                        
                        // 3. Clear application configuration in NVS
                        config_storage_clear_all();
                        
                        // 4. Force restart
                        esp_restart();
                    }



                    state[i] = BTN_STATE_IDLE;
                }
                break;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));  /* 10ms polling */
    }

    ESP_LOGI(TAG, "Button task stopped");
    vTaskDelete(NULL);
}

void button_handler_init(void)
{
    ESP_LOGI(TAG, "Initializing button handler");

    /* Configure GPIO pins as input with pull-up */
    gpio_config_t io_conf = {
        .pin_bit_mask = 0,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    for (int i = 0; i < BUTTON_NUM; i++) {
        io_conf.pin_bit_mask |= (1ULL << s_button_pins[i]);
    }

    esp_err_t ret = gpio_config(&io_conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "GPIO config failed: %s", esp_err_to_name(ret));
        return;
    }

    /* Indicator LED — simple GPIO, no RMT/DMA conflict with BT */
    gpio_set_direction(INDICATOR_LED_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(INDICATOR_LED_GPIO, 0);

    /* Start button monitoring task */
    s_btn_task_running = true;
    xTaskCreate(button_task_func, "BtnTask", BUTTON_TASK_STACK,
                NULL, BUTTON_TASK_PRIORITY, &s_btn_task_handle);

    /* Start inactivity deep sleep timer (30 min) */
    s_inactivity_timer = xTimerCreate("inact_tmr",
                                       pdMS_TO_TICKS(INACTIVITY_MS),
                                       pdFALSE, NULL, inactivity_sleep_cb);
    if (s_inactivity_timer) xTimerStart(s_inactivity_timer, 0);

    ESP_LOGI(TAG, "Button handler initialized");
}

void button_handler_deinit(void)
{
    ESP_LOGI(TAG, "Deinitializing button handler");

    s_btn_task_running = false;

    if (s_btn_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(50));
        s_btn_task_handle = NULL;
    }
}
