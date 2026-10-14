# ---- Stage 1: build the C++ server ----
FROM ubuntu:22.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake libssl-dev pkg-config \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY third-party/dji-edge-sdk third-party/dji-edge-sdk
COPY services/edge-server services/edge-server
RUN cmake -S services/edge-server -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j

# ---- Stage 2: runtime ----
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      libssl3 libcurl4 libjsoncpp25 ffmpeg \
      mosquitto supervisor python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# MediaMTX, taken from its official image (same version as the old setup)
COPY --from=bluenviron/mediamtx:1.9.3 /mediamtx /usr/local/bin/mediamtx

# Two Python environments, because paho 1.x and 2.x cannot share one.
# Collapse to one once B1 moves everything to paho 2.
COPY services/telemetry-bridge/requirements.txt /tmp/req-paho1.txt
COPY services/flight-command-bridge/requirements.txt /tmp/req-paho2.txt
RUN python3 -m venv /opt/venv-paho1 && /opt/venv-paho1/bin/pip install --no-cache-dir -r /tmp/req-paho1.txt \
 && python3 -m venv /opt/venv-paho2 && /opt/venv-paho2/bin/pip install --no-cache-dir -r /tmp/req-paho2.txt

COPY --from=build /src/build/server /app/server
COPY services/dock-handshake/dock_handshake.py      /app/
COPY services/telemetry-bridge/telemetry_bridge.py  /app/
COPY services/flight-command-bridge/bridge.py       /app/flight_command_bridge.py
COPY infrastructure/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf
COPY infrastructure/supervisord.conf /etc/supervisor/supervisord.conf

RUN mkdir -p /var/lib/mosquitto && chown mosquitto:mosquitto /var/lib/mosquitto

EXPOSE 1883 8554
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]