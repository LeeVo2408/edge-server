#ifndef __RTSP_STREAMER_H__
#define __RTSP_STREAMER_H__

#include <cstdio>
#include <cstdint>
#include <mutex>

class RTSPStreamer {
public:
    RTSPStreamer();
    ~RTSPStreamer();

    bool Start();
    void Stop();

    void PushFrame(
        const uint8_t* data,
        size_t len);

private:
    FILE*      ffmpeg_pipe_;
    std::mutex pipe_mutex_;
};

#endif
