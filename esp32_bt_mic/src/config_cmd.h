#ifndef CONFIG_CMD_H
#define CONFIG_CMD_H

#include <stddef.h>

typedef void (*cmd_respond_cb_t)(const char *data, size_t len);

void execute_config_cmd(const char *cmd_line, size_t len, cmd_respond_cb_t respond_cb);

#endif // CONFIG_CMD_H
