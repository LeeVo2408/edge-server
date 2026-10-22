#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>

#include "liveview/liveview.h"
#include "error_code.h"

#include "edge_app/rtsp_streamer.h"

namespace edge_app {

class LiveviewRelay {
public:
    LiveviewRelay();

    edge_sdk::ErrorCode Init(
        edge_sdk::Liveview::CameraType camera_type,
        edge_sdk::Liveview::StreamQuality stream_quality);

    edge_sdk::ErrorCode Start();

private:
    edge_sdk::ErrorCode HandleH264Frame(
        const uint8_t* data,
        size_t length);

    void HandleLiveviewStatus(
        const edge_sdk::Liveview::LiveviewStatus& status);

    std::shared_ptr<edge_sdk::Liveview> liveview_;

    // The detached Start() thread reads this; HandleLiveviewStatus writes
    // it -- hence the atomic to avoid a data race.
    std::atomic<bool> is_liveview_available_{false};

    RtspStreamer rtsp_streamer_;
};

}  // namespace edge_app
