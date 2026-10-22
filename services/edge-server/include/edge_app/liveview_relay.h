#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>

#include "edge_app/rtsp_streamer.h"
#include "error_code.h"
#include "liveview/liveview.h"

namespace edge_app {

// Relays the aircraft's liveview H.264 stream from the DJI Edge SDK into RTSP.
class LiveviewRelay {
public:
    LiveviewRelay();

    edge_sdk::ErrorCode Init(edge_sdk::Liveview::CameraType camera_type,
                             edge_sdk::Liveview::StreamQuality stream_quality);
    edge_sdk::ErrorCode Start();

private:
    edge_sdk::ErrorCode HandleH264Frame(const uint8_t* data, size_t length);
    void HandleLiveviewStatus(const edge_sdk::Liveview::LiveviewStatus& status);

    std::shared_ptr<edge_sdk::Liveview> liveview_;

    // Written by the SDK's status callback and read by the thread Start()
    // launches, so it must be atomic.
    std::atomic<bool> is_liveview_available_{false};

    RtspStreamer rtsp_streamer_;
};

}  // namespace edge_app
