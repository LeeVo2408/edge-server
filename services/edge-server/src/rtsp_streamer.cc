#include "edge_app/rtsp_streamer.h"

#include <iostream>
#include <string>

namespace edge_app {
namespace {

// MediaMTX runs in the same container, so FFmpeg publishes to loopback.
constexpr char kRtspPublishUrl[] = "rtsp://127.0.0.1:8554/live";

// Where clients find the stream, for the log line only.
constexpr char kRtspClientUrl[] = "rtsp://<EDGE-IP>:8554/live";

// -f h264 -i pipe:0     read raw Annex-B H.264 from stdin
// -c copy               forward NAL units as they are; no re-encode
// -rtsp_transport tcp   TCP for the RTSP data channel
//
// -re is deliberately omitted: it throttles input to native frame rate, which
// is for replaying files. On a live source it makes FFmpeg drop frames.
const std::string kFfmpegCommand =
    std::string(
        "ffmpeg -nostdin -loglevel warning -f h264 -i pipe:0 -c copy "
        "-f rtsp -rtsp_transport tcp ") +
    kRtspPublishUrl;

}  // namespace

RtspStreamer::~RtspStreamer() {
    Stop();
}

bool RtspStreamer::Start() {
    std::lock_guard<std::mutex> lock(ffmpeg_pipe_mutex_);

    ffmpeg_pipe_ = popen(kFfmpegCommand.c_str(), "w");
    if (ffmpeg_pipe_ == nullptr) {
        std::cerr << "RtspStreamer: failed to launch FFmpeg" << std::endl;
        return false;
    }

    std::cout << "RtspStreamer: stream publishing to " << kRtspClientUrl << std::endl;
    return true;
}

void RtspStreamer::Stop() {
    std::lock_guard<std::mutex> lock(ffmpeg_pipe_mutex_);
    if (ffmpeg_pipe_ != nullptr) {
        pclose(ffmpeg_pipe_);
        ffmpeg_pipe_ = nullptr;
    }
}

void RtspStreamer::PushFrame(const uint8_t* data, size_t length) {
    std::lock_guard<std::mutex> lock(ffmpeg_pipe_mutex_);
    if (ffmpeg_pipe_ == nullptr) {
        return;
    }

    // No fflush here. Per-frame fflush adds a syscall on every NAL unit
    // (~30x per second at 1080p30); the kernel pipe buffer handles buffering.
    const size_t bytes_written = fwrite(data, 1, length, ffmpeg_pipe_);

    // A short write means FFmpeg has exited. Clearing the pipe stops further
    // pushes instead of writing into a broken pipe on every frame.
    if (bytes_written != length) {
        std::cerr << "RtspStreamer: pipe write short (" << bytes_written << "/" << length
                  << " bytes), FFmpeg may have exited" << std::endl;
        pclose(ffmpeg_pipe_);
        ffmpeg_pipe_ = nullptr;
    }
}

}  // namespace edge_app
