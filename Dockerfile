# edge-server: one image running every program under supervisord.
#
# Build and run from the repository root:
#   docker compose up -d --build
#
# libedgesdk.a is aarch64-only, so this image builds for linux/arm64.

# ---------------------------------------------------------------------------
# Stage 1: build the C++ video relay against the vendored DJI Edge SDK
# ---------------------------------------------------------------------------
FROM ubuntu:22.04 AS build
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake libssl-dev pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY third-party/dji-edge-sdk third-party/dji-edge-sdk
COPY services/edge-server     services/edge-server

RUN cmake -S services/edge-server -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# ESDK runtime:   libssl3, libcurl4, libjsoncpp25
# Video relay:    ffmpeg (pushes H.264 into MediaMTX)
# Broker:         mosquitto
# Process manager: supervisor
# Bridges:        python3, python3-venv
RUN apt-get update && apt-get install -y --no-install-recommends \
      libssl3 libcurl4 libjsoncpp25 \
      ffmpeg \
      mosquitto \
      supervisor \
      python3 python3-venv \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# MediaMTX (RTSP server), taken from its official image. Pinned to the version
# the original single-container setup used.
COPY --from=bluenviron/mediamtx:1.9.3 /mediamtx /usr/local/bin/mediamtx

# Two Python environments, because paho-mqtt 1.x and 2.x cannot share one:
#   venv-paho1: dock-handshake, telemetry-bridge   (paho-mqtt 1.6.1)
#   venv-paho2: flight-command-bridge              (paho-mqtt 2.1.0)
# Requirements are copied before the code so this layer stays cached when only
# the Python sources change. Collapse to one venv once everything is on paho 2.
COPY services/dock-handshake/requirements.txt        /tmp/req-handshake.txt
COPY services/telemetry-bridge/requirements.txt      /tmp/req-telemetry.txt
COPY services/flight-command-bridge/requirements.txt /tmp/req-flight.txt
RUN python3 -m venv /opt/venv-paho1 \
 && /opt/venv-paho1/bin/pip install --no-cache-dir \
      -r /tmp/req-handshake.txt -r /tmp/req-telemetry.txt \
 && python3 -m venv /opt/venv-paho2 \
 && /opt/venv-paho2/bin/pip install --no-cache-dir -r /tmp/req-flight.txt \
 && rm /tmp/req-*.txt

# Programs
COPY --from=build /src/build/edge-server            /app/edge-server
COPY services/dock-handshake/dock_handshake.py      /app/dock_handshake.py
COPY services/telemetry-bridge/telemetry_bridge.py  /app/telemetry_bridge.py
COPY services/flight-command-bridge/flight_command_bridge.py /app/flight_command_bridge.py

# Configuration
COPY infrastructure/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf
COPY infrastructure/supervisord.conf         /etc/supervisor/supervisord.conf

# Mosquitto drops to the mosquitto user, so it must own its persistence folder.
RUN mkdir -p /var/lib/mosquitto && chown mosquitto:mosquitto /var/lib/mosquitto

# 1883 = MQTT (telemetry out, flight commands in, dock binding)
# 8554 = RTSP (live video out)
EXPOSE 1883 8554

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]