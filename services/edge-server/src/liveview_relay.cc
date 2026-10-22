#include "edge_app/liveview_relay.h"

#include <chrono>
#include <iostream>
#include <thread>

namespace edge_app {
namespace {

// The SDK reports availability through a callback but offers no call to wait
// on it, so the start-up thread polls.
constexpr std::chrono::seconds kLiveviewPollInterval{1};

}  // namespace

LiveviewRelay::LiveviewRelay()
    : liveview_(edge_sdk::CreateLiveview()) {
}

edge_sdk::ErrorCode LiveviewRelay::HandleH264Frame(
    const uint8_t* data,
    size_t length) {

    rtsp_streamer_.PushFrame(data, length);
    return edge_sdk::kOk;
}

edge_sdk::ErrorCode LiveviewRelay::Init(
    edge_sdk::Liveview::CameraType camera_type,
    edge_sdk::Liveview::StreamQuality stream_quality) {

    edge_sdk::Liveview::Options options = {
        camera_type,
        stream_quality,
        [this](const uint8_t* data, uint32_t length) {
            return HandleH264Frame(data, length);
        }
    };

    const edge_sdk::ErrorCode error_code = liveview_->Init(options);
    if (error_code != edge_sdk::kOk) {
        return error_code;
    }

    liveview_->SubscribeLiveviewStatus(
        [this](const edge_sdk::Liveview::LiveviewStatus& status) {
            HandleLiveviewStatus(status);
        });

    // Note: RtspStreamer::Start() (which spawns FFmpeg) is intentionally
    // NOT called here. It is deferred to the Start() thread, just before
    // StartH264Stream(), so FFmpeg is not left waiting on an empty pipe
    // while the liveview link is still coming up.

    return error_code;
}

edge_sdk::ErrorCode LiveviewRelay::Start() {

    std::thread([this] {
        // Wait until the ESDK signals the liveview is available.
        // Calling StartH264Stream() before this will fail.
        while (!is_liveview_available_.load()) {
            std::this_thread::sleep_for(kLiveviewPollInterval);
        }

        // Start FFmpeg immediately before requesting the stream so there
        // is a reader on the pipe when the first NAL units arrive.
        if (!rtsp_streamer_.Start()) {
            std::cerr << "LiveviewRelay: Failed to start RTSP streamer" << std::endl;
            return;
        }

        const edge_sdk::ErrorCode error_code = liveview_->StartH264Stream();
        if (error_code != edge_sdk::kOk) {
            std::cerr << "LiveviewRelay: Failed to start H264 stream: " << error_code
                      << std::endl;
        }

    }).detach();

    return edge_sdk::kOk;
}

void LiveviewRelay::HandleLiveviewStatus(
    const edge_sdk::Liveview::LiveviewStatus& status) {

    // LiveviewStatus is a uint32_t bitmask with one bit per stream quality;
    // any set bit means at least one quality is available.
    is_liveview_available_.store(status != 0);

    std::cout << "LiveviewRelay: liveview status changed: " << status << std::endl;
}

}  // namespace edge_app
