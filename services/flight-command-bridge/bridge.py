"""Flight-command bridge, stage 1: receive flight commands on the edge server.

Subscribes to dock/dock1/flight and logs every command the vROC app sends.

This stage only receives commands; it does not send anything to the drone.
Forwarding them to the DJI Cloud API (once a dock is bound to a Cloud API
server) would be added in on_message(). Until then the simulator, which
subscribes to the same topic, is what actually moves.

Config (environment variables):
  MQTT_HOST    broker address    default: localhost
  MQTT_PORT    broker port       default: 1883
"""

import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

FLIGHT_COMMAND_TOPIC = "dock/dock1/flight"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("flight-command-bridge")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        log.error("MQTT connect failed: %s", reason_code)
        return
    # Subscribing here (not once at startup) means a reconnect re-subscribes.
    client.subscribe(FLIGHT_COMMAND_TOPIC, qos=0)
    log.info("Connected to %s:%s, listening on %s", MQTT_HOST, MQTT_PORT, FLIGHT_COMMAND_TOPIC)


def on_disconnect(client, userdata, flags, reason_code, properties):
    log.warning("MQTT disconnected (%s), reconnecting", reason_code)


def on_message(client, userdata, message):
    log.info("RECEIVED %s", message.payload.decode("utf-8", errors="replace"))


def main() -> None:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"flight-command-bridge-{os.getpid()}",
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    # The broker may start after us (compose restart, VM boot); keep trying.
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            break
        except OSError as error:
            log.warning("Broker %s:%s not reachable (%s), retrying in 3s", MQTT_HOST, MQTT_PORT, error)
            time.sleep(3)

    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()