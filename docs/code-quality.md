# Code Quality

Standards for the edge-server codebase: the principles we optimise for, the
tooling that enforces them, and the naming conventions that keep the project
legible.

These are the same standards as AVP vROC's `docs/code-quality.md`, translated
from Swift to the two languages this repository uses: C++ for the video relay
(`services/edge-server`) and Python for the MQTT services
(`services/dock-handshake`, `services/telemetry-bridge`,
`services/flight-command-bridge`).

## Principles

1. **Optimise for readability.** Prefer the obvious solution over the clever one.
2. **Consistency over personal preference.** If a file already has conventions,
   follow them even where you would have chosen differently. Reworks belong in a
   dedicated `refactor/` branch.
3. **Leave code cleaner than you found it.** Fixing a name or deleting a dead
   function next to what you are already working on is encouraged. Rewriting a
   large, unrelated section should be its own PR.
4. **Flight-critical paths get more scrutiny.** Anything that sends a command to
   the aircraft (`flight-command-bridge`), or that the operator relies on to see
   the aircraft (telemetry, the video relay), is held to a higher standard than
   cosmetic work. Such changes cover failure, boundary and recovery cases, not
   just the happy path.
5. **External names are an interface.** MQTT topics, payload fields, environment
   variables and stream URLs are read by the dock, by clients and by `.env`
   files on deployed machines. Renaming one is a behaviour change, not a
   refactor: it needs its own PR and a note in the README.

## Tooling

Configuration lives at the repository root, so every tool applies exactly the
rules below. Run both before pushing:

```sh
clang-format --dry-run --Werror services/edge-server/src/*.cc services/edge-server/include/edge_app/*.h
ruff check services && ruff format --check services
```

Install with `brew install clang-format ruff` (macOS) or
`sudo apt-get install clang-format && pipx install ruff` (Ubuntu).

### C++ — clang-format

`.clang-format`. Google style, which matches the DJI Edge SDK headers we compile
against, with the 4-space indent our sources already use.

```yaml
BasedOnStyle: Google
IndentWidth: 4
ColumnLimit: 100
AccessModifierOffset: -4
AllowShortFunctionsOnASingleLine: Empty
AllowShortIfStatementsOnASingleLine: Never
DerivePointerAlignment: false
PointerAlignment: Left
IncludeBlocks: Regroup
```

`third-party/` is never reformatted.

### C++ — compiler warnings

`services/edge-server/CMakeLists.txt` builds our sources with
`-Wall -Wextra -Wpedantic -Wshadow`. The SDK headers are included as `SYSTEM`
headers, so their warnings are not ours to fix and do not appear.

The build is warning-free. Keep it that way: a new warning is a blocker, not
something to defer. `-Werror` is the next step, once CI builds the image.

### Python — Ruff

`pyproject.toml`. Ruff is both the linter and the formatter.

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "S", "BLE", "G", "RUF"]
```

`G` enforces lazy logging arguments (`log.info("x=%s", x)`, not f-strings), so a
message is only formatted when it is actually emitted. `S` and `BLE` catch
security smells and bare `except Exception`.

Every service pins its dependencies in its own `requirements.txt` with `==`. A
dependency that is declared but not imported is a defect: remove it or use it.

### Not enforced yet

- **The Python services.** `services/dock-handshake`, `services/telemetry-bridge`
  and `services/flight-command-bridge` predate this standard and do not meet it
  yet: f-strings in log calls, abbreviated names, units missing from names,
  `main()` doing everything. Each is its own `refactor/` PR. Until then, Ruff
  reports their findings rather than blocking.
- **`pyproject.toml`.** Added with the first Python refactor, using the
  configuration above.
- **Test file names.** `tests/test-*.py` still use hyphens; rename to
  `test_*.py` (and update `tests/run-all-tests.py` and `docs/tests.md`) in one PR.
- **CI.** Neither tool runs on pull requests yet; run them locally. A
  `quality` job running the two commands above is the next step.
- **clang-tidy.** Needs the CMake compile database from an aarch64 build;
  add it with the CI job.
- **Type checking.** No type checker runs on the Python yet.

## Naming conventions

### Files

- C++: `snake_case.cc` and `snake_case.h`, named for the primary type the file
  declares — `rtsp_streamer.h` declares `RtspStreamer`. This matches the SDK.
- Python: `snake_case.py`. A service's entry point is named for the service:
  `services/telemetry-bridge/telemetry_bridge.py`.
- A file is named for what it is, not for the sample it started from.

| Wrong | Correct |
|---|---|
| `liveview_rtsp_sample.cc` (production code) | `liveview_relay.cc` |
| `RTSPStreamer.cc` | `rtsp_streamer.cc` |
| `dockerfile` | `Dockerfile` |

- Test files mirror the unit under test: `rtsp_streamer_test.cc`,
  `test_telemetry_bridge.py`.

### Folders

- Top-level paths and service folders are lowercase kebab-case:
  `services/flight-command-bridge`, `third-party/dji-edge-sdk`.
- Inside a C++ service: `src/`, `include/edge_app/`, `CMakeLists.txt`. Our
  headers are included as `"edge_app/<name>.h"` so they can never collide with
  an SDK header.
- No spaces in any path segment.
- `services/` holds code we write; `infrastructure/` holds configuration only;
  `third-party/` is vendored and never edited in place.

### Types

- C++ classes are `UpperCamelCase`, and acronyms are treated as words:
  `RtspStreamer`, not `RTSPStreamer`.
- A class is named for the role it plays: `LiveviewRelay` relays liveview into
  RTSP; `RtspStreamer` streams into an RTSP server.
- Python classes, where they exist, are `UpperCamelCase`.

### Functions and variables

| | C++ | Python |
|---|---|---|
| Functions | `UpperCamelCase` verbs (`PushFrame`), matching the SDK | `snake_case` verbs (`build_position_message`) |
| Variables and parameters | `snake_case` | `snake_case` |
| Private members | `snake_case_` (trailing underscore) | `_leading_underscore` |

- Booleans read as assertions.

| Wrong | Correct |
|---|---|
| `liveview_status_ == 0` | `!is_liveview_available_` |
| `missing` (a list) | `missing_variables` |

- Spell out units in the name. Ambiguous units are dangerous.

| Wrong | Correct |
|---|---|
| `sleep(1)` | `kLiveviewPollInterval` (`std::chrono::seconds`) |
| `keepalive=60` | `KEEPALIVE_SECONDS = 60` |
| `int(time.time() * 1000)` | `timestamp_milliseconds()` |
| `h={height}m` | `height_metres` |

- Keep functions modular: one task per function. A function should not absorb
  work that belongs to another. In the Python services, building a message is a
  pure function, separate from publishing it, so it can be tested without a
  broker.
- No abbreviations except those well understood in context: `gps`, `mqtt`,
  `rtsp`, `osd`, `sn`, `url`, `id`, and the DJI protocol's own field names
  (`tid`, `bid`).

| Wrong | Correct |
|---|---|
| `lat`, `lon` | `latitude`, `longitude` |
| `rc` | `error_code`, `result`, `return_code` |
| `msg`, `e` | `message`, `error` |
| `out` | `position_message` |

- Avoid single-letter names outside a tight scope (loop indices, coordinate math).

### Constants

C++: `constexpr` with a `k` prefix, in an anonymous namespace in the `.cc` file
that uses them, or in the class that owns them.

```cpp
namespace {
// MediaMTX runs in the same container, so FFmpeg publishes to loopback.
constexpr char kRtspPublishUrl[] = "rtsp://127.0.0.1:8554/live";
}  // namespace
```

Python: `UPPER_SNAKE_CASE` at module level. Environment variables are read
once, at the top of the module, each with its default:

```python
BROKER_HOST = os.environ.get("LOCAL_BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("LOCAL_BROKER_PORT", "1883"))
KEEPALIVE_SECONDS = 60
```

A topic or URL string appears exactly once, as a named constant.

### C++ specifics

- All first-party code is in `namespace edge_app`. No `using namespace` in a
  header; prefer qualified names (`edge_sdk::kOk`) in `.cc` files too.
- Headers use `#pragma once`. Identifiers with a double underscore
  (`__RTSP_STREAMER_H__`) are reserved for the compiler.
- Prefer lambdas to `std::bind`.

## Commenting

Comments explain **why**, not **what**. The code should be self-explanatory.

Good — each comment carries information the code cannot:

```cpp
// No fflush here. Per-frame fflush adds a syscall on every NAL unit
// (~30x per second at 1080p30); the kernel pipe buffer handles buffering.
const size_t bytes_written = fwrite(data, 1, length, ffmpeg_pipe_);
```

```python
# Subscribing here rather than once at start-up means a reconnect re-subscribes.
client.subscribe(FLIGHT_COMMAND_TOPIC, qos=0)
```

Bad — the comment restates the code:

```cpp
// start the streamer
rtsp_streamer_.Start();
```

```python
# battery
battery_percent = data.get("battery")
```

A comment that describes behaviour the code no longer has is worse than no
comment. Update or delete comments in the same commit as the code they describe.

Each Python module starts with a docstring saying what the service does and
which environment variables it reads.
