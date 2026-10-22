#!/usr/bin/env python3
"""Dock handshake: lets a DJI Dock bind to this edge server.

The dock speaks the DJI Cloud API protocol over MQTT. When it is pointed at this
server's broker it publishes binding and licence requests on
``thing/product/<gateway_sn>/requests``; this service answers each one on
``thing/product/<gateway_sn>/requests_reply`` so the dock treats the local broker
as its cloud server.

Environment variables:
  LOCAL_BROKER_HOST   broker address                 default: 127.0.0.1
  LOCAL_BROKER_PORT   broker port                    default: 1883
  DJI_APP_ID          DJI Cloud API app ID           required
  DJI_APP_KEY         DJI Cloud API app key          required
  DJI_APP_LICENSE     DJI Cloud API app licence      required
  ORG_ID              organisation the dock binds to default: myorg
  ORG_NAME            organisation display name      default: My Organisation
  WORKSPACE_ID        workspace reported to the dock default: random per start
"""

import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable

import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("LOCAL_BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("LOCAL_BROKER_PORT", "1883"))
DJI_APP_ID = os.environ.get("DJI_APP_ID", "")
DJI_APP_KEY = os.environ.get("DJI_APP_KEY", "")
DJI_APP_LICENSE = os.environ.get("DJI_APP_LICENSE", "")
ORG_ID = os.environ.get("ORG_ID", "myorg")
ORG_NAME = os.environ.get("ORG_NAME", "My Organisation")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", str(uuid.uuid4()))

REQUESTS_TOPIC = "thing/product/+/requests"
NTP_SERVER_HOST = "pool.ntp.org"
CLIENT_ID = "dock_handshake"

KEEPALIVE_SECONDS = 60
RECONNECT_MIN_DELAY_SECONDS = 1
RECONNECT_MAX_DELAY_SECONDS = 15
CONNECT_RETRY_DELAY_SECONDS = 3

# DJI Cloud API: a result of 0 tells the dock the request succeeded.
RESULT_SUCCESS = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [dock_handshake] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

Request = dict
Handler = Callable[[mqtt.Client, str, Request], None]


def timestamp_milliseconds() -> int:
    return int(time.time() * 1000)


def reply_topic(gateway_sn: str) -> str:
    return f"thing/product/{gateway_sn}/requests_reply"


def gateway_sn_from_topic(topic: str) -> str | None:
    """Return the gateway serial number in ``thing/product/<sn>/requests``."""
    topic_parts = topic.split("/")
    if len(topic_parts) < 4:
        return None
    return topic_parts[2]


def build_reply(request: Request, method: str, output: dict) -> dict:
    """Wrap ``output`` in the Cloud API reply envelope for ``request``.

    The dock matches a reply to its request by ``tid`` and ``bid``, so both are
    echoed back; fresh ones are generated only if the request had none.
    """
    return {
        "tid": request.get("tid", str(uuid.uuid4())),
        "bid": request.get("bid", str(uuid.uuid4())),
        "method": method,
        "timestamp": timestamp_milliseconds(),
        "data": {
            "result": RESULT_SUCCESS,
            "output": output,
        },
    }


def build_config_output() -> dict:
    return {
        "app_id": DJI_APP_ID,
        "app_key": DJI_APP_KEY,
        "app_license": DJI_APP_LICENSE,
        "ntp_server_host": NTP_SERVER_HOST,
        "workspace_id": WORKSPACE_ID,
    }


def build_bind_status_output(devices: list[dict]) -> dict:
    """Report every device as already bound to this organisation."""
    bind_status = []
    for device in devices:
        device_sn = device.get("sn", "unknown")
        bind_status.append(
            {
                "sn": device_sn,
                "is_device_bind_organization": True,
                "organization_id": ORG_ID,
                "organization_name": ORG_NAME,
                "device_callsign": device_sn,
            }
        )
    return {"bind_status": bind_status}


def publish_reply(client: mqtt.Client, gateway_sn: str, reply: dict) -> None:
    client.publish(reply_topic(gateway_sn), json.dumps(reply), qos=0)


def handle_config(client: mqtt.Client, gateway_sn: str, request: Request) -> None:
    publish_reply(client, gateway_sn, build_reply(request, "config", build_config_output()))
    log.info("[%s] Replied to config (license verification)", gateway_sn)


def handle_airport_bind_status(client: mqtt.Client, gateway_sn: str, request: Request) -> None:
    devices = request.get("data", {}).get("devices", [])
    output = build_bind_status_output(devices)
    publish_reply(client, gateway_sn, build_reply(request, "airport_bind_status", output))
    log.info(
        "[%s] Replied to airport_bind_status (%d devices → already bound)",
        gateway_sn,
        len(devices),
    )


def handle_airport_organization_get(client: mqtt.Client, gateway_sn: str, request: Request) -> None:
    binding_code = request.get("data", {}).get("device_binding_code", "")
    log.info("[%s] airport_organization_get (binding_code=%r)", gateway_sn, binding_code)

    output = {"organization_name": ORG_NAME}
    publish_reply(client, gateway_sn, build_reply(request, "airport_organization_get", output))
    log.info("[%s] Replied to airport_organization_get", gateway_sn)


def handle_airport_organization_bind(
    client: mqtt.Client, gateway_sn: str, request: Request
) -> None:
    bind_devices = request.get("data", {}).get("bind_devices", [])
    log.info("[%s] airport_organization_bind (%d devices)", gateway_sn, len(bind_devices))

    # An empty err_infos list tells the dock every device bound successfully.
    output = {"err_infos": []}
    publish_reply(client, gateway_sn, build_reply(request, "airport_organization_bind", output))
    log.info("[%s] Replied to airport_organization_bind → bind successful", gateway_sn)


HANDLERS: dict[str, Handler] = {
    "config": handle_config,
    "airport_bind_status": handle_airport_bind_status,
    "airport_organization_get": handle_airport_organization_get,
    "airport_organization_bind": handle_airport_organization_bind,
}


def on_connect(client: mqtt.Client, userdata: object, flags: dict, return_code: int) -> None:
    if return_code != 0:
        log.error("Connection failed: rc=%s", return_code)
        return
    log.info("Connected to local broker at %s:%s", BROKER_HOST, BROKER_PORT)
    # Subscribing here rather than once at start-up means a reconnect re-subscribes.
    client.subscribe(REQUESTS_TOPIC, qos=0)
    log.info("Subscribed to: %s", REQUESTS_TOPIC)
    log.info("Ready — waiting for dock binding requests...")


def on_disconnect(client: mqtt.Client, userdata: object, return_code: int) -> None:
    if return_code != 0:
        log.warning("Unexpected disconnect (rc=%s), reconnecting...", return_code)


def on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
    gateway_sn = gateway_sn_from_topic(message.topic)
    if gateway_sn is None:
        return

    try:
        request = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("[%s] Failed to decode request: %s", gateway_sn, error)
        return

    method = request.get("method", "")
    handler = HANDLERS.get(method)
    if handler is None:
        log.debug("[%s] Unhandled method: %s", gateway_sn, method)
        return

    log.info("[%s] Received request: method=%s", gateway_sn, method)
    try:
        handler(client, gateway_sn, request)
    # Deliberately broad: one malformed request must not stop the service
    # answering the next one.
    except Exception:
        log.exception("[%s] Handler for %s raised", gateway_sn, method)


def find_missing_credentials() -> list[str]:
    credentials = {
        "DJI_APP_ID": DJI_APP_ID,
        "DJI_APP_KEY": DJI_APP_KEY,
        "DJI_APP_LICENSE": DJI_APP_LICENSE,
    }
    return [name for name, value in credentials.items() if not value]


def log_startup_banner() -> None:
    log.info("DJI Dock Handshake Service starting")
    log.info("  Broker      : %s:%s", BROKER_HOST, BROKER_PORT)
    log.info("  App ID      : %s", DJI_APP_ID)
    log.info("  Org ID      : %s", ORG_ID)
    log.info("  Workspace ID: %s", WORKSPACE_ID)
    log.info("")
    log.info("When you go to bind the dock in DJI Pilot 2, enter:")
    log.info("  MQTT Gateway : mqtt://<this-server-ip>:%s", BROKER_PORT)
    log.info("  MQTT Account : (blank, or any username if auth is enabled)")
    log.info("  Org ID       : %s", ORG_ID)
    log.info("  Binding Code : (blank, or any string)")


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
                "Cannot connect to broker: %s. Retrying in %ss...",
                error,
                CONNECT_RETRY_DELAY_SECONDS,
            )
            time.sleep(CONNECT_RETRY_DELAY_SECONDS)


def main() -> None:
    missing_credentials = find_missing_credentials()
    if missing_credentials:
        log.error("Missing required environment variables: %s", ", ".join(missing_credentials))
        log.error("Get these from developer.dji.com → Apps → your Cloud API app")
        sys.exit(1)

    log_startup_banner()
    client = create_client()
    connect_with_retry(client)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
