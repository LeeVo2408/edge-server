#include "liveview_rtsp_sample.h"

#include <thread>
#include <unistd.h>
#include <cstdio>

using namespace edge_sdk;

namespace edge_app {

LiveviewRTSPSample::LiveviewRTSPSample()
    : liveview_status_(0) {
    liveview_ = edge_sdk::CreateLiveview();
}

edge_sdk::ErrorCode LiveviewRTSPSample::StreamCallback(
    const uint8_t* data,
    size_t len) {

    rtsp_streamer_.PushFrame(data, len);
    return kOk;
}

edge_sdk::ErrorCode LiveviewRTSPSample::Init(
    Liveview::CameraType type,
    Liveview::StreamQuality quality) {

    auto stream_callback =
        std::bind(
            &LiveviewRTSPSample::StreamCallback,
            this,
            std::placeholders::_1,
            std::placeholders::_2);

    Liveview::Options option = {
        type,
        quality,
        stream_callback
    };

    auto rc = liveview_->Init(option);
    if (rc != kOk) {
        return rc;
    }

    liveview_->SubscribeLiveviewStatus(
        std::bind(
            &LiveviewRTSPSample::LiveviewStatusCallback,
            this,
            std::placeholders::_1));

    // Note: RTSPStreamer::Start() (which spawns FFmpeg) is intentionally
    // NOT called here. It is deferred to the Start() thread, just before
    // StartH264Stream(), so FFmpeg is not left waiting on an empty pipe
    // while the liveview link is still coming up.

    return rc;
}

edge_sdk::ErrorCode LiveviewRTSPSample::Start() {

    std::thread([this] {
        // Wait until the ESDK signals the liveview is available.
        // Calling StartH264Stream() before this will fail.
        while (liveview_status_.load() == 0) {
            sleep(1);
        }

        // Start FFmpeg immediately before requesting the stream so there
        // is a reader on the pipe when the first NAL units arrive.
        if (!rtsp_streamer_.Start()) {
            printf("LiveviewRTSPSample: Failed to start RTSP streamer\n");
            return;
        }

        auto rc = liveview_->StartH264Stream();
        if (rc != kOk) {
            printf("LiveviewRTSPSample: Failed to start H264 stream: %d\n", rc);
        }

    }).detach();

    return kOk;
}

void LiveviewRTSPSample::LiveviewStatusCallback(
    const Liveview::LiveviewStatus& status) {

    // LiveviewStatus is an enum; store as int for atomic compatibility.
    liveview_status_.store(static_cast<int>(status));

    printf("LiveviewRTSPSample: liveview status changed: %d\n",
           static_cast<int>(status));
}

}  // namespace edge_app
