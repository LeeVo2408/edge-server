#!/usr/bin/env python3
"""Telemetry bridge: republishes the dock's aircraft telemetry as a position message.

Subscribes to the aircraft's DJI Cloud API OSD topic
(``thing/product/<DRONE_SN>/osd``) on the local broker and publishes a flattened
position message for clients on ``LOCAL_PUBLISH_TOPIC``. Messages that are
malformed, or carry missing or impossible coordinates, are dropped.

Environment variables:
  LOCAL_BROKER_HOST     broker address             default: 127.0.0.1
  LOCAL_BROKER_PORT     broker port                default: 1883
  DRONE_SN              aircraft serial number     required
  LOCAL_PUBLISH_TOPIC   output topic               default: drone/telemetry/position
"""

import json
import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("LOCAL_BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("LOCAL_BROKER_PORT", "1883"))
DRONE_SN = os.environ.get("DRONE_SN", "")
POSITION_TOPIC = os.environ.get("LOCAL_PUBLISH_TOPIC", "drone/telemetry/position")

OSD_TOPIC = f"thing/product/{DRONE_SN}/osd"
CLIENT_ID = "telemetry_bridge"

KEEPALIVE_SECONDS = 60
RECONNECT_MIN_DELAY_SECONDS = 1
RECONNECT_MAX_DELAY_SECONDS = 30
CONNECT_RETRY_DELAY_SECONDS = 3

LATITUDE_LIMIT_DEGREES = 90
LONGITUDE_LIMIT_DEGREES = 180

# OSD fields copied unchanged into the position message, after the coordinates.
PASSTHROUGH_FIELDS = (
    "height",
    "elevation",
    "horizontal_speed",
    "vertical_speed",
    "attitude_head",
    "attitude_pitch",
    "attitude_roll",
    "mode_code",
    "position_state",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [telemetry_bridge] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def is_number(value: object) -> bool:
    # bool is a subclass of int in Python, but True is not a coordinate.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_valid_coordinate(latitude: float, longitude: float) -> bool:
    # Chained comparisons are False for NaN, so NaN is rejected here too.
    return (
        -LATITUDE_LIMIT_DEGREES <= latitude <= LATITUDE_LIMIT_DEGREES
        and -LONGITUDE_LIMIT_DEGREES <= longitude <= LONGITUDE_LIMIT_DEGREES
    )


def has_gps_fix(latitude: float, longitude: float) -> bool:
    # The aircraft reports exactly (0, 0) until it has a GPS fix. One zero
    # coordinate alone is valid: the equator or the prime meridian.
    return not (latitude == 0.0 and longitude == 0.0)


def extract_osd_data(osd_envelope: object) -> dict | None:
    """Return the envelope's ``data`` object, or None if the structure is wrong."""
    if not isinstance(osd_envelope, dict):
        log.warning("Skipping OSD: message must be an object")
        return None

    osd_data = osd_envelope.get("data", {})
    if not isinstance(osd_data, dict):
        log.warning("Skipping OSD: data must be an object")
        return None
    return osd_data


def build_position_message(osd_envelope: object, drone_sn: str) -> dict | None:
    """Flatten a DJI OSD envelope into a position message.

    Returns None when the OSD carries no usable position: a malformed
    structure, missing or invalid coordinates, or no GPS fix yet.
    """
    osd_data = extract_osd_data(osd_envelope)
    if osd_data is None:
        return None

    latitude = osd_data.get("latitude")
    longitude = osd_data.get("longitude")

    if latitude is None or longitude is None:
        return None
    if not is_number(latitude) or not is_number(longitude):
        log.warning("Skipping OSD: coordinates must be numbers")
        return None
    if not is_valid_coordinate(latitude, longitude):
        log.warning("Skipping OSD: coordinates outside valid ranges")
        return None
    if not has_gps_fix(latitude, longitude):
        log.debug("Skipping OSD: no GPS fix yet (lat=0, lon=0)")
        return None

    position_message = {
        "timestamp": osd_envelope.get("timestamp"),
        "drone_sn": drone_sn,
        "latitude": latitude,
        "longitude": longitude,
    }
    for field in PASSTHROUGH_FIELDS:
        position_message[field] = osd_data.get(field)
    return position_message


def on_connect(client: mqtt.Client, userdata: object, flags: dict, return_code: int) -> None:
    if return_code != 0:
        log.error("Connection to local broker failed: rc=%s", return_code)
        return
    log.info("Connected to local broker at %s:%s", BROKER_HOST, BROKER_PORT)
    log.info("Subscribing to OSD topic: %s", OSD_TOPIC)
    # Subscribing here rather than once at start-up means a reconnect re-subscribes.
    client.subscribe(OSD_TOPIC, qos=0)


def on_disconnect(client: mqtt.Client, userdata: object, return_code: int) -> None:
    if return_code != 0:
        log.warning("Unexpected disconnect from local broker (rc=%s). Reconnecting...", return_code)


def on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
    try:
        osd_envelope = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("Failed to decode OSD message: %s", error)
        return

    position_message = build_position_message(osd_envelope, DRONE_SN)
    if position_message is None:
        return

    result = client.publish(POSITION_TOPIC, json.dumps(position_message), qos=0, retain=False)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning("Publish failed: rc=%s", result.rc)
        return
    log.debug(
        "Published: latitude=%.6f longitude=%.6f height_metres=%s",
        position_message["latitude"],
        position_message["longitude"],
        position_message["height"],
    )


def log_startup_banner() -> None:
    log.info("DJI Telemetry Bridge starting")
    log.info("  Local broker  : %s:%s", BROKER_HOST, BROKER_PORT)
    log.info("  Subscribing   : %s", OSD_TOPIC)
    log.info("  Publishing    : %s", POSITION_TOPIC)


def create_client() -> mqtt.Client:
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(
        min_delay=RECONNECT_MIN_DELAY_SECONDS, max_delay=RECONNECT_MAX_DELAY_SECONDS
    )
    return client


def connect_with_retry(client: mqtt.Client) -> None:
    # The broker may start after us (container start, VM boot); keep trying.
    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=KEEPALIVE_SECONDS)
            return
        except OSError as error:
            log.warning(
                "Cannot connect to local broker: %s. Retrying in %ss...",
                error,
                CONNECT_RETRY_DELAY_SECONDS,
            )
            time.sleep(CONNECT_RETRY_DELAY_SECONDS)


def main() -> None:
    if not DRONE_SN:
        log.error("DRONE_SN environment variable is not set")
        sys.exit(1)

    log_startup_banner()
    client = create_client()
    connect_with_retry(client)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
