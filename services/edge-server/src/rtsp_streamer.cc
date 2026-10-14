#include "edge_app/rtsp_streamer.h"

#include <iostream>
#include <cstdio>

RTSPStreamer::RTSPStreamer()
    : ffmpeg_pipe_(nullptr) {
}

RTSPStreamer::~RTSPStreamer() {
    Stop();
}

bool RTSPStreamer::Start() {
    // Notes on flags:
    //   -f h264       : treat stdin as a raw Annex-B H.264 stream
    //   -i -          : read from stdin (the pipe)
    //   -c copy       : no re-encode; forward NAL units as-is
    //   -f rtsp       : output via RTSP publish
    //   -rtsp_transport tcp : use TCP for the RTSP data channel
    //
    // Deliberately omitted:
    //   -re           : "read at native frame rate" -- that flag is for
    //                   playing back files, not for live push. Including
    //                   it on a live source causes FFmpeg to throttle
    //                   and drop incoming frames.
    const char* cmd =
        "ffmpeg "
        "-nostdin "
        "-loglevel warning "
        "-f h264 "
        "-i pipe:0 "
        "-c copy "
        "-f rtsp "
        "-rtsp_transport tcp "
        "rtsp://127.0.0.1:8554/live";

    std::lock_guard<std::mutex> lock(pipe_mutex_);

    ffmpeg_pipe_ = popen(cmd, "w");
    if (!ffmpeg_pipe_) {
        std::cerr << "RTSPStreamer: Failed to launch FFmpeg\n";
        return false;
    }

    std::cout << "RTSPStreamer: stream publishing to rtsp://<EDGE-IP>:8554/live\n";
    return true;
}

void RTSPStreamer::Stop() {
    std::lock_guard<std::mutex> lock(pipe_mutex_);
    if (ffmpeg_pipe_) {
        pclose(ffmpeg_pipe_);
        ffmpeg_pipe_ = nullptr;
    }
}

void RTSPStreamer::PushFrame(
    const uint8_t* data,
    size_t len) {

    std::lock_guard<std::mutex> lock(pipe_mutex_);
    if (!ffmpeg_pipe_) return;

    // fwrite returns the number of items written; a short write means the
    // pipe broke (FFmpeg exited). Log and clear so callers stop pushing.
    size_t written = fwrite(data, 1, len, ffmpeg_pipe_);
    if (written != len) {
        std::cerr << "RTSPStreamer: pipe write short (" << written
                  << "/" << len << ") -- FFmpeg may have exited\n";
        pclose(ffmpeg_pipe_);
        ffmpeg_pipe_ = nullptr;
    }
    // No fflush here. Per-frame fflush adds a syscall on every NAL unit
    // (~30x per second at 1080p30). The kernel pipe buffer handles
    // buffering; FFmpeg reads as fast as data arrives.
}
