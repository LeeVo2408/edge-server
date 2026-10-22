cmake_minimum_required(VERSION 3.10)

project(edge_server)

set(CMAKE_CXX_STANDARD 17)

set(SDK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../third-party/dji-edge-sdk)

set(SOURCES
    src/main.cc
    src/liveview_relay.cc
    src/rtsp_streamer.cc
)

add_executable(server ${SOURCES})

target_include_directories(server PRIVATE
    include
    ${SDK_DIR}/include
)

target_link_libraries(server
    ${SDK_DIR}/lib/aarch64/libedgesdk.a
    crypto
    pthread
    dl
    rt
)