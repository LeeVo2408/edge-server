#ifndef __LIVEVIEW_RTSP_SAMPLE_H__
#define __LIVEVIEW_RTSP_SAMPLE_H__

#include <atomic>
#include <chrono>

#include "liveview/liveview.h"
#include "error_code.h"

#include "rtsp_streamer.h"

namespace edge_app {

class LiveviewRTSPSample {
public:
    LiveviewRTSPSample();

    edge_sdk::ErrorCode Init(
        edge_sdk::Liveview::CameraType type,
        edge_sdk::Liveview::StreamQuality quality);

    edge_sdk::ErrorCode Start();

private:
    edge_sdk::ErrorCode StreamCallback(
        const uint8_t* data,
        size_t len);

    void LiveviewStatusCallback(
        const edge_sdk::Liveview::LiveviewStatus& status);

    std::shared_ptr<edge_sdk::Liveview> liveview_;

    // Stored as int so std::atomic<> works without a custom specialisation.
    // The detached Start() thread reads this; LiveviewStatusCallback writes
    // it -- hence the atomic to avoid a data race.
    std::atomic<int> liveview_status_;

    RTSPStreamer rtsp_streamer_;
};

}  // namespace edge_app

#endif  // __LIVEVIEW_RTSP_SAMPLE_H__
