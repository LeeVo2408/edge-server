#!/usr/bin/env python3
"""Flight-command bridge, stage 1: receive flight commands on the edge server.

Subscribes to ``dock/dock1/flight`` and logs every command a client sends.

This stage only receives commands; nothing is sent to the aircraft yet.
Forwarding them to the dock as DJI Cloud API service calls is the next stage,
and will be added in ``on_message``.

Environment variables:
  MQTT_HOST   broker address   default: localhost
  MQTT_PORT   broker port      default: 1883
"""

import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))

FLIGHT_COMMAND_TOPIC = "dock/dock1/flight"

KEEPALIVE_SECONDS = 30
RECONNECT_MIN_DELAY_SECONDS = 1
RECONNECT_MAX_DELAY_SECONDS = 10
CONNECT_RETRY_DELAY_SECONDS = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("flight-command-bridge")


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if reason_code.is_failure:
        log.error("MQTT connect failed: %s", reason_code)
        return
    # Subscribing here rather than once at start-up means a reconnect re-subscribes.
    client.subscribe(FLIGHT_COMMAND_TOPIC, qos=0)
    log.info("Connected to %s:%s, listening on %s", BROKER_HOST, BROKER_PORT, FLIGHT_COMMAND_TOPIC)


def on_disconnect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.DisconnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    log.warning("MQTT disconnected (%s), reconnecting", reason_code)


def on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
    log.info("RECEIVED %s", message.payload.decode("utf-8", errors="replace"))


def create_client() -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"flight-command-bridge-{os.getpid()}",
    )
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
                "Broker %s:%s not reachable (%s), retrying in %ss",
                BROKER_HOST,
                BROKER_PORT,
                error,
                CONNECT_RETRY_DELAY_SECONDS,
            )
            time.sleep(CONNECT_RETRY_DELAY_SECONDS)


def main() -> None:
    client = create_client()
    connect_with_retry(client)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
