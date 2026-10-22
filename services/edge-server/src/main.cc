#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

#include "edge_app/liveview_relay.h"

namespace {

// Dock-based aircraft (M3D, M30) carry the mission camera as the payload
// camera. kCameraTypeFpv may return no stream on dock deployments.
constexpr edge_sdk::Liveview::CameraType kCameraType = edge_sdk::Liveview::kCameraTypePayload;
constexpr edge_sdk::Liveview::StreamQuality kStreamQuality =
    edge_sdk::Liveview::kStreamQuality1080pHigh;

// The SDK delivers frames on its own threads; main only has to stay alive.
constexpr std::chrono::seconds kIdleInterval{1};

}  // namespace

int main() {
    std::cout << "Starting Edge RTSP Server" << std::endl;

    edge_app::LiveviewRelay liveview_relay;

    edge_sdk::ErrorCode error_code = liveview_relay.Init(kCameraType, kStreamQuality);
    if (error_code != edge_sdk::kOk) {
        std::cerr << "Liveview init failed: " << error_code << std::endl;
        return EXIT_FAILURE;
    }

    error_code = liveview_relay.Start();
    if (error_code != edge_sdk::kOk) {
        std::cerr << "Liveview start failed: " << error_code << std::endl;
        return EXIT_FAILURE;
    }

    std::cout << "Running. RTSP stream will be available at rtsp://<EDGE-IP>:8554/live once "
                 "the drone connects."
              << std::endl;

    while (true) {
        std::this_thread::sleep_for(kIdleInterval);
    }
}
