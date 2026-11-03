#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <mutex>

namespace edge_app {

class RtspStreamer {
public:
    RtspStreamer() = default;
    ~RtspStreamer();

    // Copying would leave two objects closing the same FFmpeg pipe.
    RtspStreamer(const RtspStreamer&) = delete;
    RtspStreamer& operator=(const RtspStreamer&) = delete;

    bool Start();
    void Stop();

    void PushFrame(const uint8_t* data, size_t length);

private:
    FILE* ffmpeg_pipe_ = nullptr;
    std::mutex ffmpeg_pipe_mutex_;
};

}  // namespace edge_app
