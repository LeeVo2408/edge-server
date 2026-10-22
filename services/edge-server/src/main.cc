#include <chrono>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <thread>

#include "edge_app/liveview_relay.h"

using namespace edge_app;

namespace {

// Camera type selection:
//   kCameraTypeFpv     -- FPV (forward-facing) camera.
//   kCameraTypePayload -- Primary payload camera (e.g. Zenmuse on
//                         DJI Dock / Dock 2 missions).
//
// DJI Dock 1 / Dock 2 drones (e.g. M3D, M30) use kCameraTypePayload
// for the main mission camera. kCameraTypeFpv may return no stream on
// dock-based deployments. Change this to match your hardware.
constexpr edge_sdk::Liveview::CameraType kCameraType =
    edge_sdk::Liveview::CameraType::kCameraTypePayload;

constexpr edge_sdk::Liveview::StreamQuality kStreamQuality =
    edge_sdk::Liveview::StreamQuality::kStreamQuality1080pHigh;

// The SDK delivers frames on its own threads; main only has to stay alive.
constexpr std::chrono::seconds kIdleInterval{1};

}  // namespace

int main() {
    std::cout << "Starting Edge RTSP Server\n";

    auto liveview = std::make_shared<LiveviewRelay>();

    edge_sdk::ErrorCode error_code = liveview->Init(kCameraType, kStreamQuality);
    if (error_code != edge_sdk::kOk) {
        std::cerr << "Liveview init failed: " << error_code << "\n";
        return EXIT_FAILURE;
    }

    error_code = liveview->Start();
    if (error_code != edge_sdk::kOk) {
        std::cerr << "Liveview start failed: " << error_code << "\n";
        return EXIT_FAILURE;
    }

    std::cout << "Running. RTSP stream will be available at "
                 "rtsp://<EDGE-IP>:8554/live once the drone connects.\n";

    while (true) {
        std::this_thread::sleep_for(kIdleInterval);
    }
}
