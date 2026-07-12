#ifndef SPP_SERVER_H
#define SPP_SERVER_H

#include "esp_err.h"

esp_err_t spp_server_init(void);
void spp_server_send_event_btn(uint8_t btn_id, uint8_t state);
void spp_server_send_event_status(uint8_t hfp_connected, uint8_t audio_active);

#endif // SPP_SERVER_H
