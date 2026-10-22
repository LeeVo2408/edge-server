cmake_minimum_required(VERSION 3.16)

project(edge_server LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Lets editors and clang-tidy see the real include paths and flags.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(SDK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../third-party/dji-edge-sdk)

# DJI ships libedgesdk.a per architecture. The edge VM is aarch64; x86_64 is
# supported so the code can also be built on an Intel machine.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
    set(SDK_ARCH aarch64)
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64)$")
    set(SDK_ARCH x86_64)
else()
    message(FATAL_ERROR "No libedgesdk.a for ${CMAKE_SYSTEM_PROCESSOR}")
endif()

add_executable(edge-server
    src/main.cc
    src/liveview_relay.cc
    src/rtsp_streamer.cc
)

target_include_directories(edge-server PRIVATE include)

# SYSTEM: warnings inside DJI's headers are not ours to fix.
target_include_directories(edge-server SYSTEM PRIVATE ${SDK_DIR}/include)

target_compile_options(edge-server PRIVATE -Wall -Wextra -Wpedantic -Wshadow)

# Order matters: GNU ld resolves left to right, so crypto must come after
# libedgesdk.a, which depends on it.
target_link_libraries(edge-server PRIVATE
    ${SDK_DIR}/lib/${SDK_ARCH}/libedgesdk.a
    crypto
    pthread
    dl
    rt
)
