# FPV EdgeServer Testing Guide

Author: Nima Nadali Jelokhani  
Results recorded: 19 October 2026

## 1. Purpose and scope

This work covers the requested EdgeServer tests:

- Container health and process crash recovery.
- MQTT broker connectivity from the VM and another network machine.
- Telemetry bridge handling of valid, invalid, and edge-case messages.
- Flight-command bridge behaviour.
- Dock handshake behaviour, excluding the `config` method.

It includes both integration tests and unit tests.

**Unit tests** call Python functions with fake inputs and mocked MQTT clients. They
need no real broker, drone, or DJI server.

**Integration tests** interact with the actual Docker container or MQTT broker.
They require those services to be running.

## 2. Files created and changed

```text
tests/
  run_all_tests.py
  test_container_health.py
  test_broker.py
  test_telemetry_bridge.py
  test_flight_command_bridge.py
  test_dock_handshake.py
```

Production source changed:

```text
services/telemetry-bridge/telemetry_bridge.py
```

The telemetry change adds message and coordinate validation. The other bridges
were tested without changing their production behaviour.

## 3. Recorded results

The latest run completed with:

| Result | Count |
| --- | ---: |
| Passed | 65 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 5 |

These results were supplied from the user's local execution. They are not evidence
of testing on a real dock or across the required remote machines.

| Suite | Latest result |
| --- | --- |
| Container | 6 passed, 5 skipped |
| Broker | 1 passed locally |
| Telemetry | 30 passed |
| Flight commands | 11 passed |
| Dock handshake | 17 passed |

Both process crash-recovery tests passed in an earlier run using `--crash`.
They were not enabled in the latest run. Earlier telemetry results were 19 passed
and 11 failed; after the validation fix, all 30 telemetry cases passed.

A skipped check is **not verified coverage**. Exit code `0` means the selected run
had no failures, but it can still contain skipped checks.

## 4. Environment and dependencies

The bridges use different Paho MQTT versions:

| Environment | Dependency | Used by |
| --- | --- | --- |
| `/tmp/fpv-test-venv` | `paho-mqtt==1.6.1` | Telemetry and dock tests; container tests |
| `/tmp/fpv-flight-test-venv` | `paho-mqtt==2.1.0` | Flight-command and broker tests |

Both environments also need `pytest`. Separate environments preserve compatibility
with each bridge's MQTT callback API.

The temporary environments were used after pip stalled while reading files inside
the project's original `.venv`. Their use resolved the installation blockage, but
the underlying filesystem or environment issue was not diagnosed.

**Temporary environments may disappear after cleanup or a restart.** Recreate them
when necessary. The runner currently contains these absolute interpreter paths;
other developers must create equivalent environments or update those paths.

Run from the project root, one command at a time:

```bash
python3 -m venv /tmp/fpv-test-venv
/tmp/fpv-test-venv/bin/python -m pip install pytest 'paho-mqtt==1.6.1'
python3 -m venv /tmp/fpv-flight-test-venv
/tmp/fpv-flight-test-venv/bin/python -m pip install pytest 'paho-mqtt==2.1.0'
```

The container tests require Docker and the test container to be running. The broker
test requires a reachable broker. Unit tests do not require either.

## 5. Container health and crash recovery

File: `tests/test_container_health.py`

Type: integration tests.

The Compose service is `edge-server`. Supervisor manages Mosquitto, MediaMTX,
dock-handshake, telemetry-bridge, flight-command-bridge, and the ESDK server.
The container has no Docker `HEALTHCHECK`, so a running container alone does not
prove that its internal programs are functioning.

### Health checks

| Test | What it verifies |
| --- | --- |
| `test_container_is_running` | Docker reports the container as running. |
| `test_restart_policy` | The configured policy is `unless-stopped`. |
| `test_supervisor_responds` | Supervisor returns a process ID through its socket. |
| `test_process_is_running` | Each selected program reports `RUNNING`. |

The process-state test has six cases, one for each Supervisor program.

By default, the following three cases are skipped:

- `dock-handshake`: full-stack mode is disabled; missing DJI credentials caused
  its observed startup failure.
- `telemetry-bridge`: full-stack mode is disabled. Its earlier `FATAL` startup state
  was not diagnosed from logs. The unit-test validation fix does not establish that
  this startup problem is resolved.
- `edge-server`: requires a configured environment and a dock to remain running.

`TEST_FULL_STACK=1` enables these checks; it does not configure the services or make
missing dependencies available.

### Process recovery checks

`test_process_recovers_after_crash` has two cases: Mosquitto and MediaMTX.

For each process, the test:

1. Checks that it is already running and records its PID.
2. Records the container start time and restart count.
3. Sends `KILL` through Supervisor to simulate a process crash.
4. Waits for a different PID in the `RUNNING` state.
5. Checks that the replacement remains running for another three seconds.
6. Checks that the entire container did not restart.

The recovery loop allows approximately 60 seconds, although Docker command timeouts
can extend the total duration. Each command has its own timeout.

These tests briefly interrupt MQTT or video. Run them only on a test deployment.
They depend on Supervisor to recover the process; they do not repair a failed service.

They prove **process recovery**, not whole-container crash recovery. Checking a restart
policy is not equivalent to crashing and recovering the entire container.

They do not prove video playback resumes after MediaMTX restarts. The runner's later
broker test checks message delivery after the container suite, but does not measure
continuous connectivity or client reconnection during the crash.

## 6. MQTT broker connectivity

File: `tests/test_broker.py`

Type: integration test.

The supplied broker configuration listens on all interfaces on port `1883` and
allows anonymous connections. The test uses that configuration without credentials.

`test_broker_delivers_message`:

1. Creates a unique topic under `tests/fpv/`.
2. Connects a subscriber and waits for the subscription acknowledgement.
3. Connects a separate publisher.
4. Publishes a non-retained QoS 0 test message.
5. Checks that the subscriber receives the exact topic and payload.
6. Disconnects both clients in cleanup.

It never publishes to a flight-command, telemetry, or dock-handshake topic.

Configuration:

| Variable | Default |
| --- | --- |
| `TEST_BROKER_HOST` | `localhost` |
| `TEST_BROKER_PORT` | `1883` |

The local execution passed. The VM and other-machine checks remain pending.
The same test must actually execute from each requested location; changing the host
address while staying on the Mac does not prove access from another machine.

This test does not verify retained-message persistence, authentication, TLS, or
internet/Starlink access.

## 7. Telemetry bridge unit tests

File: `tests/test_telemetry_bridge.py`

Source: `services/telemetry-bridge/telemetry_bridge.py`

The fixture loads the real module with fake settings and never calls `main()`.
A mocked MQTT client records `subscribe()` and `publish()` calls without a network.

| Test | Cases | Expected behaviour |
| --- | ---: | --- |
| `test_successful_connection_subscribes` | 1 | Subscribe to the configured drone OSD topic. |
| `test_failed_connection_does_not_subscribe` | 1 | Do not subscribe after connection failure. |
| `test_valid_message_is_forwarded` | 1 | Preserve mapped fields, topic, QoS and retain setting. |
| `test_invalid_payload_is_ignored` | 4 | Ignore invalid JSON, truncated JSON, empty bytes and bad UTF-8. |
| `test_missing_coordinates_or_no_fix_are_ignored` | 6 | Ignore missing/null coordinates and `(0, 0)`. |
| `test_valid_coordinate_boundaries` | 4 | Accept one zero coordinate and valid geographic limits. |
| `test_missing_optional_fields_become_null` | 1 | Include absent optional output fields as JSON null. |
| `test_publish_failure_is_logged` | 1 | Log an unsuccessful MQTT publish result. |
| `test_invalid_message_structure_is_ignored` | 4 | Ignore list/null envelopes and list/null data. |
| `test_invalid_coordinates_are_rejected` | 7 | Reject text, boolean and out-of-range coordinates. |

Total: **30 cases**.

The six missing-coordinate/no-fix cases are an empty data object, missing latitude,
missing longitude, null latitude, null longitude, and both coordinates equal to zero.

Valid boundary cases are `(0, 20)`, `(10, 0)`, `(90, 180)`, and `(-90, -180)`.
The current bridge treats `(0, 0)` as no GPS fix; this is existing application behaviour.

Invalid-coordinate cases include text in either coordinate, boolean latitude,
latitude outside `[-90, 90]`, and longitude outside `[-180, 180]`.

### Bugs found and production fix

The original bridge produced 11 failures:

- Four malformed structures raised exceptions when `.get()` was called on a list
  or `None`.
- Two text-coordinate messages were passed to `publish()` and then raised exceptions
  during numeric log formatting.
- Five boolean/out-of-range cases were forwarded instead of rejected.

Validation was added inside `on_message()`, before the existing `(0, 0)` check and
before publishing:

```python
    if not isinstance(envelope, dict):
        log.warning("Skipping OSD: message must be an object")
        return

    data = envelope.get("data", {})
    if not isinstance(data, dict):
        log.warning("Skipping OSD: data must be an object")
        return

    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        return

    if type(lat) not in (int, float) or type(lon) not in (int, float):
        log.warning("Skipping OSD: coordinates must be numbers")
        return

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        log.warning("Skipping OSD: coordinates outside valid ranges")
        return
```

A bad message is discarded; the bridge can process the next valid message.
The input topic, output topic, and normal message mapping are unchanged.

The range check also rejects NaN and infinity, but dedicated tests for those values
have not been added. Validation of optional fields such as height is not covered by
this change.

The actual service still requires a broker, a configured `DRONE_SN`, and incoming
OSD messages. Messages may come from a simulator. This change does not generate data
or remove runtime dependencies.

The unit tests load the edited source directly. A Docker image containing an older
copy must be rebuilt/redeployed before the running service uses this fix.

## 8. Flight-command bridge unit tests

File: `tests/test_flight_command_bridge.py`

Source: `services/flight-command-bridge/flight_command_bridge.py`

This is a **stage-1 receive-and-log bridge**. It does not validate commands or forward
commands to DJI. Tests check that documented behaviour rather than inventing a
forwarding requirement for code that does not implement it.

| Test | Cases | Expected behaviour |
| --- | ---: | --- |
| `test_successful_connection_subscribes` | 1 | Subscribe to `dock/dock1/flight`. |
| `test_failed_connection_does_not_subscribe` | 1 | Log connection failure without subscribing. |
| `test_reconnection_subscribes_again` | 1 | Subscribe again on a subsequent successful connection. |
| `test_disconnect_is_logged` | 1 | Log the disconnect callback. |
| `test_received_payload_is_logged` | 5 | Log received text without forwarding it. |
| `test_main_configures_client` | 1 | Set callbacks, connection settings and reconnect delay. |
| `test_main_retries_when_broker_is_unavailable` | 1 | Retry two failed connections, then enter the loop. |

Total: **11 cases**, all passed.

The five payload cases are JSON text, non-JSON text, empty bytes, invalid UTF-8,
and Persian text. Invalid UTF-8 is replaced during decoding, matching the source.
The JSON example is illustrative text, not proof of a validated command schema.

Startup tests mock the MQTT client constructor. The retry test also mocks sleep, so
there is no real connection or waiting. The disconnect test checks logging; it does
not prove automatic reconnection over a real network.

## 9. Dock-handshake unit tests

File: `tests/test_dock_handshake.py`

The fixture searches `services/` for exactly one `dock_handshake.py`, loads it with
fake organization settings and blank DJI credential values, and does not call `main()`.

**The `config` method is excluded entirely.** The actual project's `handle_config`
function remains unchanged. The test fixture replaces both the function reference
and its routing-table entry with a blocker. No config request is sent. The fixture
also verifies that the blocker was never called.

| Test | Cases | Expected behaviour |
| --- | ---: | --- |
| `test_connection_subscribes` | 1 | Subscribe to `thing/product/+/requests`. |
| `test_failed_connection_does_not_subscribe` | 1 | Do not subscribe on connection failure. |
| `test_bind_status_reply` | 4 | Build expected device entries and reply metadata. |
| `test_organization_get_reply` | 1 | Return the test organization name. |
| `test_organization_bind_reply` | 2 | Return the implemented success reply. |
| `test_invalid_payload_is_ignored` | 4 | Ignore malformed JSON, empty bytes and bad UTF-8. |
| `test_unknown_method_is_ignored` | 2 | Ignore unknown and empty method names. |
| `test_short_topic_is_ignored` | 1 | Ignore a topic with too few segments. |
| `test_handler_error_is_logged` | 1 | Catch and log an error from a non-config handler. |

Total: **17 cases**, all passed.

Bind-status cases cover zero devices, one device, two devices, and a device without
an `sn`. The missing serial falls back to `unknown`. The timestamp is fixed in the
test so reply metadata can be checked exactly.

The handlers currently report successful binding without verifying it with DJI.
These tests prove reply construction and local routing, not real device binding.
They do not comprehensively test every malformed decoded JSON structure or topic.

## 10. Running all tests

File: `tests/run_all_tests.py`

From the project root:

```bash
python3 tests/run_all_tests.py
```

Include deliberate process crash recovery on a test deployment:

```bash
python3 tests/run_all_tests.py --crash
```

Enable the three full-stack process checks only when their dependencies are configured:

```bash
python3 tests/run_all_tests.py --full-stack
```

Both flags can be combined. The runner does not start Docker, install dependencies,
or populate configuration files.

The runner:

1. Finds each test file beside itself in `tests/`.
2. Selects the appropriate Paho environment.
3. Runs each suite and generates a temporary JUnit XML report.
4. Reads the report and prints individual test results.
5. Continues to later suites when one suite fails.
6. Prints totals and returns a failure exit code for failed/incomplete runs.

Output meanings:

| Label | Meaning |
| --- | --- |
| `PASSED` | The executed test's assertions passed. |
| `FAILED` | An executed test did not meet its assertions or raised an exception. |
| `ERROR` | A setup, teardown, or collection error prevented normal completion. |
| `SKIPPED` | The check was deliberately not executed. |
| `NOT RUN` | The runner could not find a file or its Python environment. |

The runner captures pytest output while each suite executes, so there can be a pause
before individual results appear. Its temporary XML files are deleted at the end.
It does not currently save a permanent detailed report or print failure tracebacks.
Run the failing suite directly to see those details.

## 11. Running individual suites

Run from the project root:

```bash
/tmp/fpv-test-venv/bin/python -m pytest tests/test_container_health.py -v --tb=short
/tmp/fpv-test-venv/bin/python -m pytest tests/test_telemetry_bridge.py -v --tb=short
/tmp/fpv-flight-test-venv/bin/python -m pytest tests/test_flight_command_bridge.py -v --tb=short
/tmp/fpv-test-venv/bin/python -m pytest tests/test_dock_handshake.py -v --tb=short
/tmp/fpv-flight-test-venv/bin/python -m pytest tests/test_broker.py -v --tb=short
```

The filenames contain hyphens. The commands explicitly select them; default pytest
file discovery may not pick up `test-*.py` without configuration.

## 12. Broker checks on the required machines

On each machine, obtain the test file and install pytest with Paho 2.x in a suitable
Python environment. The `/tmp` environments on the Mac are not shared with other machines.

From the VM hosting the reachable broker:

```bash
TEST_BROKER_HOST=127.0.0.1 python -m pytest tests/test_broker.py -v --tb=short
```

From a different machine on the network:

```bash
TEST_BROKER_HOST="BROKER_VM_IP" python -m pytest tests/test_broker.py -v --tb=short
```

Replace `BROKER_VM_IP` with the VM's reachable address. If the broker is hosted
elsewhere, use that host's reachable address instead. The broker's port must be
reachable through the VM and network configuration.

Record the execution machine, broker destination, date, and result for each run.
A local pass alone does not complete these two required checks.

## 13. Remaining work and limits

- Run and record broker access from the VM and a separate network machine.
- Resolve/configure the three skipped full-stack process checks where possible.
- Record the earlier successful Mosquitto and MediaMTX process recovery results.
- Clarify whether the requested crash-recovery scope also requires a whole-container
  crash test; that test has not been implemented.
- Rebuild/redeploy the container when the telemetry fix must run inside Docker.

All current unit tests and the selected local integration checks pass. But it is still
local and needs real-world testing.
