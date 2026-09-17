import logging
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app import models, realtime, settings as app_settings
from app.config import MQTT_TOPIC_FILTER
from app.database import SessionLocal

logger = logging.getLogger("labmanager.mqtt")

MQTT_STATUS = {
    "connected": False,
    "last_message": None,
    "last_error": None,
    "messages": 0,
    "ignored": 0,
}

_client = None
_thread = None
_stop = threading.Event()


def _parse_value(payload: bytes):
    try:
        return float(payload.decode().strip())
    except (UnicodeDecodeError, ValueError):
        pass
    text = payload.decode(errors="ignore").strip().lower()
    if text in ("true", "1", "on", "yes"):
        return 1.0
    if text in ("false", "0", "off", "no"):
        return 0.0
    return None


def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        MQTT_STATUS["connected"] = True
        MQTT_STATUS["last_error"] = None
        client.subscribe(MQTT_TOPIC_FILTER, qos=0)
        logger.info("MQTT conectado a %s:%s, suscrito a %r", app_settings.mqtt_host(), app_settings.mqtt_port(), MQTT_TOPIC_FILTER)
    else:
        MQTT_STATUS["connected"] = False
        MQTT_STATUS["last_error"] = str(reason_code)
        logger.error("MQTT: falló la conexión (%s)", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties):
    MQTT_STATUS["connected"] = False
    logger.warning("MQTT desconectado (código %s). Reintentando...", reason_code)


def _on_message(client, userdata, msg):
    MQTT_STATUS["last_message"] = datetime.now(timezone.utc)
    value = _parse_value(msg.payload)
    if value is None:
        MQTT_STATUS["ignored"] += 1
        logger.warning("Payload no reconocido en %s: %r", msg.topic, msg.payload[:80])
        return

    session = SessionLocal()
    try:
        sensor = (
            session.query(models.Sensor)
            .filter(
                models.Sensor.mqtt_topic == msg.topic,
                models.Sensor.is_active.is_(True),
            )
            .first()
        )
        if sensor is None:
            MQTT_STATUS["ignored"] += 1
            logger.info("Ignorado %s: sensor no registrado", msg.topic)
            return
        now = datetime.now(timezone.utc)
        session.add(
            models.SensorData(time=now, sensor_id=sensor.id, value=value)
        )
        sensor.last_value = value
        sensor.last_time = now
        session.commit()
        MQTT_STATUS["messages"] += 1
        realtime.publish({
            "sensor_id": sensor.id,
            "value": value,
            "time": int(now.timestamp() * 1000),
        })
    except Exception:
        session.rollback()
        MQTT_STATUS["last_error"] = "error guardando en DB"
        logger.exception("Error guardando lectura de %s", msg.topic)
    finally:
        session.close()


def _run(client: mqtt.Client, stop: threading.Event):
    while not stop.is_set():
        try:
            client.connect(app_settings.mqtt_host(), app_settings.mqtt_port(), keepalive=60)
            client.loop_forever()
        except Exception as exc:
            MQTT_STATUS["last_error"] = str(exc)
            logger.exception("MQTT: error de conexión, reintento en 5s")
        time.sleep(5)


def start_ingestor():
    global _client, _thread, _stop
    if _thread and _thread.is_alive():
        return
    _stop = threading.Event()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="labmanager-ingestor"
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    _client = client
    _thread = threading.Thread(
        target=_run, args=(client, _stop), daemon=True, name="mqtt-ingestor"
    )
    _thread.start()
    logger.info("Ingestor MQTT iniciado")


def stop_ingestor():
    global _client, _thread, _stop
    if _stop:
        _stop.set()
    if _client:
        try:
            _client.disconnect()
        except Exception:
            pass
    if _thread:
        _thread.join(timeout=2)
    _client = None
    _thread = None
    _stop = None


def restart_ingestor():
    stop_ingestor()
    start_ingestor()
