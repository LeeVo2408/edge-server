#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
import uuid

import paho.mqtt.client as mqtt

LOCAL_HOST   = os.environ.get("LOCAL_BROKER_HOST", "127.0.0.1")
LOCAL_PORT   = int(os.environ.get("LOCAL_BROKER_PORT", "1883"))
APP_ID       = os.environ.get("DJI_APP_ID", "")
APP_KEY      = os.environ.get("DJI_APP_KEY", "")
APP_LICENSE  = os.environ.get("DJI_APP_LICENSE", "")
ORG_ID       = os.environ.get("ORG_ID", "myorg")
ORG_NAME     = os.environ.get("ORG_NAME", "My Organisation")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", str(uuid.uuid4()))

REQUESTS_TOPIC = "thing/product/+/requests"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [dock_handshake] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def _reply_topic(gateway_sn: str) -> str:
    return f"thing/product/{gateway_sn}/requests_reply"


def _base_reply(tid: str, bid: str, method: str) -> dict:
    return {
        "tid":       tid,
        "bid":       bid,
        "method":    method,
        "timestamp": int(time.time() * 1000),
    }


def handle_config(client, gateway_sn: str, msg: dict) -> None:
    tid = msg.get("tid", str(uuid.uuid4()))
    bid = msg.get("bid", str(uuid.uuid4()))

    reply = _base_reply(tid, bid, "config")
    reply["data"] = {
        "result": 0,
        "output": {
            "app_id":          APP_ID,
            "app_key":         APP_KEY,
            "app_license":     APP_LICENSE,
            "ntp_server_host": "pool.ntp.org",
            "workspace_id":    WORKSPACE_ID,
        }
    }

    topic = _reply_topic(gateway_sn)
    client.publish(topic, json.dumps(reply), qos=0)
    log.info(f"[{gateway_sn}] Replied to config (license verification)")


def handle_airport_bind_status(client, gateway_sn: str, msg: dict) -> None:
    tid = msg.get("tid", str(uuid.uuid4()))
    bid = msg.get("bid", str(uuid.uuid4()))
    devices = msg.get("data", {}).get("devices", [])

    bind_status = []
    for device in devices:
        sn = device.get("sn", "unknown")
        bind_status.append({
            "sn":                          sn,
            "is_device_bind_organization": True,
            "organization_id":             ORG_ID,
            "organization_name":           ORG_NAME,
            "device_callsign":             sn,
        })

    reply = _base_reply(tid, bid, "airport_bind_status")
    reply["data"] = {
        "result": 0,
        "output": {
            "bind_status": bind_status
        }
    }

    client.publish(_reply_topic(gateway_sn), json.dumps(reply), qos=0)
    log.info(f"[{gateway_sn}] Replied to airport_bind_status ({len(devices)} devices → already bound)")


def handle_airport_organization_get(client, gateway_sn: str, msg: dict) -> None:
    tid = msg.get("tid", str(uuid.uuid4()))
    bid = msg.get("bid", str(uuid.uuid4()))
    binding_code = msg.get("data", {}).get("device_binding_code", "")

    log.info(f"[{gateway_sn}] airport_organization_get (binding_code={binding_code!r})")

    reply = _base_reply(tid, bid, "airport_organization_get")
    reply["data"] = {
        "result": 0,
        "output": {
            "organization_name": ORG_NAME
        }
    }

    client.publish(_reply_topic(gateway_sn), json.dumps(reply), qos=0)
    log.info(f"[{gateway_sn}] Replied to airport_organization_get")


def handle_airport_organization_bind(client, gateway_sn: str, msg: dict) -> None:
    tid = msg.get("tid", str(uuid.uuid4()))
    bid = msg.get("bid", str(uuid.uuid4()))
    bind_devices = msg.get("data", {}).get("bind_devices", [])

    log.info(f"[{gateway_sn}] airport_organization_bind ({len(bind_devices)} devices)")

    reply = _base_reply(tid, bid, "airport_organization_bind")
    reply["data"] = {
        "result": 0,
        "output": {
            "err_infos": []   # empty = no errors, all devices bound successfully
        }
    }

    client.publish(_reply_topic(gateway_sn), json.dumps(reply), qos=0)
    log.info(f"[{gateway_sn}] Replied to airport_organization_bind → bind successful")


HANDLERS = {
    "config":                    handle_config,
    "airport_bind_status":       handle_airport_bind_status,
    "airport_organization_get":  handle_airport_organization_get,
    "airport_organization_bind": handle_airport_organization_bind,
}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"Connected to local broker at {LOCAL_HOST}:{LOCAL_PORT}")
        client.subscribe(REQUESTS_TOPIC, qos=0)
        log.info(f"Subscribed to: {REQUESTS_TOPIC}")
        log.info("Ready — waiting for dock binding requests...")
    else:
        log.error(f"Connection failed: rc={rc}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        log.warning(f"Unexpected disconnect (rc={rc}), reconnecting...")


def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) < 4:
        return
    gateway_sn = parts[2]

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning(f"[{gateway_sn}] Failed to decode request: {e}")
        return

    method = payload.get("method", "")
    handler = HANDLERS.get(method)

    if handler:
        log.info(f"[{gateway_sn}] Received request: method={method}")
        try:
            handler(client, gateway_sn, payload)
        except Exception as e:
            log.error(f"[{gateway_sn}] Handler for {method} raised: {e}", exc_info=True)
    else:
        log.debug(f"[{gateway_sn}] Unhandled method: {method}")


def main():
    missing = [k for k, v in {
        "DJI_APP_ID":      APP_ID,
        "DJI_APP_KEY":     APP_KEY,
        "DJI_APP_LICENSE": APP_LICENSE,
    }.items() if not v]

    if missing:
        log.error(f"Missing required environment variables: {', '.join(missing)}")
        log.error("Get these from developer.dji.com → Apps → your Cloud API app")
        sys.exit(1)

    log.info("DJI Dock Handshake Service starting")
    log.info(f"  Broker      : {LOCAL_HOST}:{LOCAL_PORT}")
    log.info(f"  App ID      : {APP_ID}")
    log.info(f"  Org ID      : {ORG_ID}")
    log.info(f"  Workspace ID: {WORKSPACE_ID}")
    log.info("")
    log.info("When you go to bind the dock in DJI Pilot 2, enter:")
    log.info(f"  MQTT Gateway : mqtt://<this-server-ip>:1883")
    log.info(f"  MQTT Account : (blank, or any username if auth is enabled)")
    log.info(f"  Org ID       : {ORG_ID}")
    log.info(f"  Binding Code : (blank, or any string)")

    client = mqtt.Client(client_id="dock_handshake", protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=15)

    while True:
        try:
            client.connect(LOCAL_HOST, LOCAL_PORT, keepalive=60)
            break
        except Exception as e:
            log.warning(f"Cannot connect to broker: {e}. Retrying in 3s...")
            time.sleep(3)

    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
