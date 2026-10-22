#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <mutex>

namespace edge_app {

// Pipes a raw H.264 stream into an FFmpeg process that publishes it to the
// local MediaMTX server over RTSP.
class RtspStreamer {
public:
    RtspStreamer() = default;
    ~RtspStreamer();

    RtspStreamer(const RtspStreamer&) = delete;
    RtspStreamer& operator=(const RtspStreamer&) = delete;

    bool Start();
    void Stop();
    void PushFrame(const uint8_t* data, size_t length);

private:
    // nullptr until Start() succeeds, and again once FFmpeg exits.
    FILE* ffmpeg_pipe_ = nullptr;
    std::mutex ffmpeg_pipe_mutex_;
};

}  // namespace edge_app
