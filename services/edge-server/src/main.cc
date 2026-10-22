#include <iostream>
#include <thread>
#include <chrono>

#include "edge_app/liveview_relay.h"

using namespace edge_app;

int main() {
    std::cout << "Starting Edge RTSP Server\n";

    auto liveview = std::make_shared<LiveviewRelay>();

    // Camera type selection:
    //   kCameraTypeFpv     -- FPV (forward-facing) camera.
    //   kCameraTypePayload -- Primary payload camera (e.g. Zenmuse on
    //                         DJI Dock / Dock 2 missions).
    //
    // DJI Dock 1 / Dock 2 drones (e.g. M3D, M30) use kCameraTypePayload
    // for the main mission camera. kCameraTypeFpv may return no stream on
    // dock-based deployments. Change this to match your hardware.
    auto rc = liveview->Init(
        edge_sdk::Liveview::CameraType::kCameraTypePayload,
        edge_sdk::Liveview::StreamQuality::kStreamQuality1080pHigh);

    if (rc != edge_sdk::kOk) {
        std::cerr << "Liveview init failed: " << rc << "\n";
        return -1;
    }

    rc = liveview->Start();
    if (rc != edge_sdk::kOk) {
        std::cerr << "Liveview start failed: " << rc << "\n";
        return -1;
    }

    std::cout << "Running. RTSP stream will be available at "
                 "rtsp://<EDGE-IP>:8554/live once the drone connects.\n";

    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}
