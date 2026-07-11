#ifndef CLASSIC_HIDD_H
#define CLASSIC_HIDD_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t classic_hidd_init(void);
bool classic_hidd_is_connected(void);
void classic_hidd_send_key(uint8_t modifier, uint8_t key_code);
void classic_hidd_release_key(void);

#endif // CLASSIC_HIDD_H
