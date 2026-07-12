cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS src)
set(PROJECT_VER "1.0.3")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_bt_mic)

add_custom_command(
    TARGET ${CMAKE_PROJECT_NAME}.elf
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy
            "${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin"
            "${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}_v${PROJECT_VER}.bin"
    COMMENT "Generating version-stamped binary: ${CMAKE_PROJECT_NAME}_v${PROJECT_VER}.bin"
)

