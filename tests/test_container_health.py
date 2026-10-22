"""Simple integration tests for container health and process recovery."""

import os
import subprocess
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_CONFIG = "/etc/supervisor/supervisord.conf"

# Enable these only when the required environment is configured.
FULL_STACK = os.getenv("TEST_FULL_STACK") == "1"
CRASH_TESTS = os.getenv("TEST_CRASH_RECOVERY") == "1"


def run(*args):
    """Run a command and return its output."""
    try:
        return subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        pytest.fail("Docker command was not found.", pytrace=False)
    except subprocess.TimeoutExpired:
        pytest.fail("Docker command timed out.", pytrace=False)


@pytest.fixture(scope="module")
def container():
    """Find the existing edge-server container."""
    result = run(
        "docker", "compose", "ps", "--all", "--quiet", "edge-server"
    )
    if result.returncode != 0:
        pytest.fail("Cannot query Docker Compose.", pytrace=False)

    ids = result.stdout.split()
    assert len(ids) == 1, "Start the edge-server test container first."
    return ids[0]


def inspect(container, template):
    """Read one Docker property without reading credentials."""
    result = run("docker", "inspect", "--format", template, container)
    if result.returncode != 0:
        pytest.fail("Cannot inspect the container.", pytrace=False)
    return result.stdout.strip()


def supervisor(container, *args):
    """Send a command to Supervisor inside the container."""
    return run(
        "docker", "exec", container,
        "supervisorctl", "-c", SUPERVISOR_CONFIG, *args,
    )


def process_state(container, name):
    """Return RUNNING, STARTING, FATAL, or another Supervisor state."""
    result = supervisor(container, "status", name)
    fields = result.stdout.split()

    if len(fields) >= 2 and fields[0] == name:
        return fields[1]

    return "UNKNOWN"


def process_pid(container, name):
    """Return the process ID, or zero if the process is unavailable."""
    result = supervisor(container, "pid", name)
    value = result.stdout.strip()
    if result.returncode == 0 and value.isdigit():
        return int(value)
    return 0


def test_container_is_running(container):
    """The container must be running."""
    assert inspect(container, "{{.State.Status}}") == "running"


def test_restart_policy(container):
    """Docker must use the configured restart policy."""
    assert inspect(
        container, "{{.HostConfig.RestartPolicy.Name}}"
    ) == "unless-stopped"


def test_supervisor_responds(container):
    """Supervisor must respond through its control socket."""
    result = supervisor(container, "pid")
    assert result.returncode == 0, "Supervisor did not respond."
    assert result.stdout.strip().isdigit(), "Invalid Supervisor PID."


@pytest.mark.parametrize(
    "name",
    [
        "mosquitto",
        "mediamtx",
        "flight-command-bridge",
        pytest.param(
            "dock-handshake",
            marks=pytest.mark.skipif(
                not FULL_STACK,
                reason="Full-stack configuration is not enabled.",
            ),
        ),
        pytest.param(
            "telemetry-bridge",
            marks=pytest.mark.skipif(
                not FULL_STACK,
                reason="Full-stack configuration is not enabled.",
            ),
        ),
        pytest.param(
            "edge-server",
            marks=pytest.mark.skipif(
                not FULL_STACK,
                reason="Requires a configured environment and dock.",
            ),
        ),
    ],
)
def test_process_is_running(container, name):
    """Check each selected process is running."""
    state = process_state(container, name)
    assert state == "RUNNING", f"{name} is {state}, expected RUNNING."


@pytest.mark.skipif(
    not CRASH_TESTS,
    reason="Set TEST_CRASH_RECOVERY=1 on a local test deployment.",
)
@pytest.mark.parametrize("name", ["mosquitto", "mediamtx"])
def test_process_recovers_after_crash(container, name):
    """Crash a process and verify Supervisor starts a replacement."""
    assert process_state(container, name) == "RUNNING", (
        f"{name} must be running before testing recovery."
    )

    old_pid = process_pid(container, name)
    assert old_pid > 0, "Could not get the original process ID."

    # Record container state to distinguish a process restart
    # from a restart of the entire container.
    original_started_at = inspect(container, "{{.State.StartedAt}}")
    original_restart_count = inspect(container, "{{.RestartCount}}")

    # KILL simulates an unexpected crash.
    # Unlike 'supervisorctl stop', it allows automatic recovery.
    result = supervisor(container, "signal", "KILL", name)
    if result.returncode != 0:
        pytest.fail(f"Could not send the crash signal to {name}.",
                    pytrace=False)

    # Give Supervisor up to 60 seconds to start a new process.
    deadline = time.monotonic() + 60
    recovered = False

    while time.monotonic() < deadline:
        state = process_state(container, name)
        new_pid = process_pid(container, name)

        if state == "RUNNING" and new_pid > 0 and new_pid != old_pid:
            recovered = True
            break

        time.sleep(1)

    assert recovered, f"{name} did not recover within 60 seconds."

    # Check that the replacement stays running briefly.
    time.sleep(3)
    assert process_state(container, name) == "RUNNING", (
        f"{name} stopped again after recovery."
    )
    assert process_pid(container, name) == new_pid, (
        f"{name} restarted again instead of remaining stable."
    )

    assert inspect(container, "{{.State.StartedAt}}") == original_started_at, (
        "The entire container restarted during the test."
    )
    assert inspect(container, "{{.RestartCount}}") == original_restart_count, (
        "Docker restarted the container during the test."
    )