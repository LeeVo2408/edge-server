#include "edge_app/rtsp_streamer.h"

#include <cstdio>
#include <iostream>
#include <string>

namespace edge_app {
namespace {

// MediaMTX runs in the same container, so FFmpeg publishes to loopback.
constexpr char kRtspPublishUrl[] = "rtsp://127.0.0.1:8554/live";

// Notes on flags:
//   -f h264       : treat stdin as a raw Annex-B H.264 stream
//   -i pipe:0     : read from stdin (the pipe)
//   -c copy       : no re-encode; forward NAL units as-is
//   -f rtsp       : output via RTSP publish
//   -rtsp_transport tcp : use TCP for the RTSP data channel
//
// Deliberately omitted:
//   -re           : "read at native frame rate" -- that flag is for
//                   playing back files, not for live push. Including
//                   it on a live source causes FFmpeg to throttle
//                   and drop incoming frames.
const std::string kFfmpegCommand =
    std::string(
        "ffmpeg "
        "-nostdin "
        "-loglevel warning "
        "-f h264 "
        "-i pipe:0 "
        "-c copy "
        "-f rtsp "
        "-rtsp_transport tcp ") +
    kRtspPublishUrl;

}  // namespace

RtspStreamer::~RtspStreamer() {
    Stop();
}

bool RtspStreamer::Start() {
    std::lock_guard<std::mutex> lock(ffmpeg_pipe_mutex_);

    ffmpeg_pipe_ = popen(kFfmpegCommand.c_str(), "w");
    if (ffmpeg_pipe_ == nullptr) {
        std::cerr << "RtspStreamer: Failed to launch FFmpeg\n";
        return false;
    }

    std::cout << "RtspStreamer: stream publishing to rtsp://<EDGE-IP>:8554/live\n";
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

    // fwrite returns the number of items written; a short write means the
    // pipe broke (FFmpeg exited). Log and clear so callers stop pushing.
    const size_t bytes_written = fwrite(data, 1, length, ffmpeg_pipe_);
    if (bytes_written != length) {
        std::cerr << "RtspStreamer: pipe write short (" << bytes_written << "/" << length
                  << ") -- FFmpeg may have exited\n";
        pclose(ffmpeg_pipe_);
        ffmpeg_pipe_ = nullptr;
    }
    // No fflush here. Per-frame fflush adds a syscall on every NAL unit
    // (~30x per second at 1080p30). The kernel pipe buffer handles
    // buffering; FFmpeg reads as fast as data arrives.
}

}  // namespace edge_app
