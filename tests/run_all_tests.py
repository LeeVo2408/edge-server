"""Run all test files and print individual results."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

PAHO1 = "/tmp/fpv-test-venv/bin/python"
PAHO2 = "/tmp/fpv-flight-test-venv/bin/python"

SUITES = [
    ("Container", "test_container_health", PAHO1),
    ("Broker", "test_broker", PAHO2),
    ("Telemetry", "test_telemetry_bridge", PAHO1),
    ("Flight commands", "test_flight_command_bridge", PAHO2),
    ("Dock handshake", "test_dock_handshake", PAHO1),
]


def find_test(name):
    """Find a test beside this runner in the tests folder."""
    folder = Path(__file__).resolve().parent
    filename = name + ".py"
    path = folder / filename
    return path if path.is_file() else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crash", action="store_true")
    parser.add_argument("--full-stack", action="store_true")
    parser.add_argument("--broker-host", default="localhost")
    args = parser.parse_args()

    env = os.environ.copy()
    env["TEST_CRASH_RECOVERY"] = "1" if args.crash else "0"
    env["TEST_FULL_STACK"] = "1" if args.full_stack else "0"
    env["TEST_BROKER_HOST"] = args.broker_host

    totals = {"PASSED": 0, "FAILED": 0, "ERROR": 0, "SKIPPED": 0}
    runner_errors = []

    with tempfile.TemporaryDirectory(prefix="fpv-results-") as directory:
        for index, (label, filename, python) in enumerate(SUITES):
            print(f"\n--- {label} ---", flush=True)

            test_file = find_test(filename)

            if test_file is None:
                print("NOT RUN: test file missing or duplicated.")
                runner_errors.append(label)
                continue

            if not Path(python).is_file():
                print("NOT RUN: Python environment missing.")
                runner_errors.append(label)
                continue

            report = Path(directory) / f"results-{index}.xml"

            try:
                result = subprocess.run(
                    [
                        python, "-m", "pytest",
                        str(test_file),
                        "-q",
                        f"--junitxml={report}",
                        "-o", "junit_logging=no",
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                print("NOT RUN: could not start Python.")
                runner_errors.append(label)
                continue

            if not report.exists():
                print("ERROR: pytest did not produce a results report.")
                runner_errors.append(label)
                continue

            try:
                cases = ET.parse(report).getroot().findall(".//testcase")
            except ET.ParseError:
                print("ERROR: results report could not be read.")
                runner_errors.append(label)
                continue

            if not cases:
                print("NOT RUN: no tests were found.")
                runner_errors.append(label)
                continue

            suite_has_failures = False

            for case in cases:
                name = case.get("name", "Unnamed test")

                if case.find("error") is not None:
                    status = "ERROR"
                elif case.find("failure") is not None:
                    status = "FAILED"
                elif case.find("skipped") is not None:
                    status = "SKIPPED"
                else:
                    status = "PASSED"

                totals[status] += 1
                print(f"{status:7}  {name}")

                if status in ("ERROR", "FAILED"):
                    suite_has_failures = True

            # Catch unsuccessful runs not explained by individual failures.
            if result.returncode != 0 and not suite_has_failures:
                print(f"RUN ERROR: pytest exited with code {result.returncode}.")
                runner_errors.append(label)

    print("\n========== TOTALS ==========")
    for status, count in totals.items():
        print(f"{status:7}: {count}")

    if runner_errors:
        print("Incomplete/error suites: " + ", ".join(runner_errors))

    print("\nSKIPPED means not tested, not passed.")

    unsuccessful = totals["FAILED"] or totals["ERROR"] or runner_errors
    return 1 if unsuccessful else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted: test run is incomplete.")
        raise SystemExit(130)