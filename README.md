# edge-server

The edge server for the DJI Dock: it runs on an ARM64 Linux machine next to the
dock, relays the aircraft's live video as RTSP, translates the dock's telemetry
onto a local MQTT broker, and receives flight commands from operator clients.

Everything runs in **one Docker container**, with each program managed by
[supervisord](http://supervisord.org/) so that a crash in one part restarts
that part alone.

## What runs inside the container

| Program | Language | What it does |
|---|---|---|
| `mosquitto` | (Eclipse Mosquitto) | Local MQTT broker on `:1883`. The dock, the bridges and clients all connect here |
| `mediamtx` | (MediaMTX 1.9.3) | RTSP server on `:8554`. FFmpeg publishes the drone video here; clients pull from here |
| `dock-handshake` | Python | Answers the dock's DJI Cloud API binding and `config` requests, so the dock treats this broker as its cloud server |
| `telemetry-bridge` | Python | Reads the dock's OSD telemetry (`thing/product/<DRONE_SN>/osd`) and republishes a simplified position message |
| `flight-command-bridge` | Python | Receives flight commands from clients on `dock/dock1/flight`. Stage 1: logs them only, nothing is sent to the aircraft yet |
| `edge-server` | C++ | Uses the DJI Edge SDK to receive the aircraft's H.264 live stream and pipes it through FFmpeg into MediaMTX |

```text
                ┌──────────────────────── edge-server container ────────────────────────┐
 DJI Dock ──MQTT──▶ mosquitto :1883 ◀──▶ dock-handshake                                  │
    │           │        ▲   ▲                                                           │
    │           │        │   └── telemetry-bridge   (thing/product/<sn>/osd → drone/…)   │
    │           │        └────── flight-command-bridge  (dock/dock1/flight)              │
    │           │                                                                        │
    └─ESDK video──▶ edge-server (C++) ──ffmpeg──▶ mediamtx :8554 ──RTSP──▶ clients       │
                └────────────────────────────────────────────────────────────────────────┘
```

## Interfaces

| What | Where | Direction |
|---|---|---|
| Live video | `rtsp://<EDGE-IP>:8554/live` | out to clients |
| Telemetry | MQTT `<EDGE-IP>:1883`, topic `drone/telemetry/position` | out to clients |
| Flight commands | MQTT `<EDGE-IP>:1883`, topic `dock/dock1/flight`, e.g. `{"action":"rth"}` | in from clients |
| Dock binding | MQTT `thing/product/+/requests` → `…/requests_reply` | dock ↔ dock-handshake |
| Dock telemetry | MQTT `thing/product/<DRONE_SN>/osd` | dock → telemetry-bridge |

## Repository structure

```text
edge-server/
├── Dockerfile                  # builds the single image (C++ build stage + runtime stage)
├── docker-compose.yml          # runs it; start everything from the repo root
├── .clang-format               # C++ formatting rules
├── pyproject.toml              # Python lint and format rules (Ruff)
├── infrastructure/             # configuration for software we don't write
│   ├── .env.example            # every setting the container reads (copy to .env)
│   ├── supervisord.conf        # which programs run, in what order, restart policy
│   └── mosquitto/
│       └── mosquitto.conf      # broker configuration
├── services/                   # our code, one folder per program
│   ├── dock-handshake/         # dock_handshake.py + requirements.txt
│   ├── edge-server/            # C++ video relay: CMakeLists.txt, src/, include/edge_app/
│   ├── flight-command-bridge/  # flight_command_bridge.py + requirements.txt
│   └── telemetry-bridge/       # telemetry_bridge.py + requirements.txt
├── third-party/
│   └── dji-edge-sdk/           # vendored DJI Edge SDK: headers, libedgesdk.a, init code
└── docs/                       # code quality, git rules, documenting changes
```

`services/` holds code we write and maintain; `infrastructure/` holds
configuration and wiring only. `third-party/` is vendored and not edited in
place; any local change is recorded in its README.

## Requirements

- An **ARM64 (aarch64) Linux** host: `libedgesdk.a` is built for aarch64. The
  team VM is Ubuntu 22.04 ARM64.
- **Docker** with the **Compose v2 plugin** (`docker compose`, with a space).
  The old `docker-compose` v1 does not support this file.
- For real video and telemetry: a DJI Dock on the same network, bound to this
  server (see [Binding the dock](#binding-the-dock)).

Building on an Apple Silicon Mac works as a build check, but `network_mode: host`
does not behave the same on Docker Desktop. Run the real thing on Linux.

## Quick start

```sh
git clone git@github.com:LeeVo2408/edge-server.git
cd edge-server

cp infrastructure/.env.example infrastructure/.env
nano infrastructure/.env          # fill in the values (see Configuration)

docker compose up -d --build
docker compose exec edge-server supervisorctl status
```

Every program except `edge-server` should show `RUNNING`. Without a dock
connected, `edge-server` exits with `Liveview init failed` and supervisord
retries it with backoff. That is expected.

## Configuration

All settings come from `infrastructure/.env`, which is git-ignored. Only
`infrastructure/.env.example` is committed. Never put real values in the example
file or in any committed file.

| Variable | Used by | Meaning |
|---|---|---|
| `DRONE_SN` | telemetry-bridge | Aircraft serial number; selects the OSD topic to read |
| `LOCAL_BROKER_HOST`, `LOCAL_BROKER_PORT` | telemetry-bridge, dock-handshake | Broker address (default `127.0.0.1:1883`) |
| `LOCAL_PUBLISH_TOPIC` | telemetry-bridge | Output topic (default `drone/telemetry/position`) |
| `MQTT_HOST`, `MQTT_PORT` | flight-command-bridge | Broker address (default `127.0.0.1:1883`) |
| `DJI_APP_ID`, `DJI_APP_KEY`, `DJI_APP_LICENSE` | dock-handshake | DJI **Cloud API** app credentials (developer.dji.com → Apps). Required |
| `ORG_ID`, `ORG_NAME` | dock-handshake | Organisation the dock is bound to |
| `WORKSPACE_ID` | dock-handshake | Set once and keep it; a new value makes the dock see a new workspace |

## Operating it

```sh
docker compose logs -f                                         # all programs, prefixed by name
docker compose exec edge-server supervisorctl status           # state of each program
docker compose exec edge-server supervisorctl restart telemetry-bridge
docker compose down                                            # stop
docker compose up -d --build                                   # rebuild after code changes
```

To move the image to a machine without building there:

```sh
docker save edge-server-edge-server -o edge-server.tar
scp edge-server.tar <user>@<edge-host>:
ssh <user>@<edge-host> docker load -i edge-server.tar
```

## Testing without hardware

Telemetry bridge, end to end. In one terminal:

```sh
docker compose exec edge-server mosquitto_sub -t 'drone/telemetry/position' -v
```

In another, publish a fake dock message (use the `DRONE_SN` from your `.env`):

```sh
docker compose exec edge-server mosquitto_pub -t 'thing/product/<DRONE_SN>/osd' \
  -m '{"timestamp":1,"data":{"latitude":-33.88,"longitude":151.21,"height":50}}'
```

The first terminal should print the translated message.

Flight-command bridge:

```sh
docker compose exec edge-server mosquitto_pub -t 'dock/dock1/flight' -m '{"action":"rth"}'
docker compose logs edge-server | grep RECEIVED
```

Dock handshake (uses a method whose reply contains no credentials):

```sh
docker compose exec edge-server mosquitto_sub -t 'thing/product/+/requests_reply' -v &
docker compose exec edge-server mosquitto_pub -t 'thing/product/TESTSN/requests' \
  -m '{"tid":"t1","bid":"b1","method":"airport_organization_get","data":{}}'
```

## Binding the dock

With the container running, bind the dock in DJI Pilot 2 using:

- MQTT gateway: `mqtt://<EDGE-IP>:1883`
- Organisation ID: the `ORG_ID` from `.env`

`dock-handshake` logs each request it answers. Once bound, the dock publishes
OSD telemetry to the broker and the telemetry bridge starts translating it.

## Known limitations

- **No broker authentication.** Mosquitto accepts anonymous connections, and
  the `config` reply to the dock contains the DJI app key. Use only on a trusted
  network until broker auth is added.
- **`ESDKInit()` is not called yet.** The C++ server starts liveview without
  initialising the SDK first.
- **Flight commands are logged, not executed.** The bridge does not yet forward
  anything to the aircraft or validate payloads.
- **Two Python environments** exist inside the image because
  `flight-command-bridge` uses paho-mqtt 2.x and the other two scripts use 1.x.
- **The image is aarch64 only.** `docker-compose.yml` builds for `linux/arm64`.
  The C++ server itself also builds natively on x86_64 against
  `third-party/dji-edge-sdk/lib/x86_64/`, which is useful for checking a change
  on an Intel machine.

## Code quality

Standards are in [docs/code-quality.md](docs/code-quality.md). Before pushing:

```sh
clang-format --dry-run --Werror services/edge-server/src/*.cc services/edge-server/include/edge_app/*.h
ruff check services && ruff format --check services
```

## Documentation

- [Code quality](docs/code-quality.md): standards, tooling and naming conventions
- [Git rules and procedures](docs/git-rules-and-procedures.md): branching, commits, pull requests
- [Documenting changes](docs/documenting-changes.md): what to update when behaviour changes
- [DJI Edge SDK](third-party/dji-edge-sdk/README.md): the vendored SDK
