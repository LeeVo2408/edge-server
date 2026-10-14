#!/usr/bin/env python3
import json
import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

LOCAL_HOST    = os.environ.get("LOCAL_BROKER_HOST",   "127.0.0.1")
LOCAL_PORT    = int(os.environ.get("LOCAL_BROKER_PORT", "1883"))
DRONE_SN      = os.environ.get("DRONE_SN", "")
PUBLISH_TOPIC = os.environ.get("LOCAL_PUBLISH_TOPIC", "drone/telemetry/position")

OSD_TOPIC = f"thing/product/{DRONE_SN}/osd"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [telemetry_bridge] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"Connected to local broker at {LOCAL_HOST}:{LOCAL_PORT}")
        log.info(f"Subscribing to OSD topic: {OSD_TOPIC}")
        client.subscribe(OSD_TOPIC, qos=0)
    else:
        log.error(f"Connection to local broker failed: rc={rc}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        log.warning(f"Unexpected disconnect from local broker (rc={rc}). Reconnecting...")


def on_message(client, userdata, msg):
    try:
        envelope = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning(f"Failed to decode OSD message: {e}")
        return

    data = envelope.get("data", {})
    lat  = data.get("latitude")
    lon  = data.get("longitude")

    if lat is None or lon is None:
        return

    if lat == 0.0 and lon == 0.0:
        log.debug("Skipping OSD: no GPS fix yet (lat=0, lon=0)")
        return

    out = {
        "timestamp":        envelope.get("timestamp"),
        "drone_sn":         DRONE_SN,
        "latitude":         lat,
        "longitude":        lon,
        "height":           data.get("height"),
        "elevation":        data.get("elevation"),
        "horizontal_speed": data.get("horizontal_speed"),
        "vertical_speed":   data.get("vertical_speed"),
        "attitude_head":    data.get("attitude_head"),
        "attitude_pitch":   data.get("attitude_pitch"),
        "attitude_roll":    data.get("attitude_roll"),
        "mode_code":        data.get("mode_code"),
        "position_state":   data.get("position_state"),
    }

    result = client.publish(PUBLISH_TOPIC, json.dumps(out), qos=0, retain=False)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning(f"Publish failed: rc={result.rc}")
    else:
        log.debug(f"Published: lat={lat:.6f} lon={lon:.6f} h={data.get('height')}m")


def main():
    if not DRONE_SN:
        log.error("DRONE_SN environment variable is not set")
        sys.exit(1)

    log.info("DJI Telemetry Bridge starting")
    log.info(f"  Local broker  : {LOCAL_HOST}:{LOCAL_PORT}")
    log.info(f"  Subscribing   : {OSD_TOPIC}")
    log.info(f"  Publishing    : {PUBLISH_TOPIC}")

    client = mqtt.Client(client_id="telemetry_bridge", protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while True:
        try:
            client.connect(LOCAL_HOST, LOCAL_PORT, keepalive=60)
            break
        except Exception as e:
            log.warning(f"Cannot connect to local broker: {e}. Retrying in 3s...")
            time.sleep(3)

    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()