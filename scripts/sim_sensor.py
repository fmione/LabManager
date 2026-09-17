#!/usr/bin/env python3
"""Simula un sensor MQTT para LabManager.

Publica en el topic `dispositivo/sensor` (ej. reactor1/temperature) el valor
crudo que espera el ingestor, con ruido gaussiano para simular un sensor real.

Uso:
    python scripts/sim_sensor.py --topic reactor1/temperature --base 25 --noise 0.5 --interval 1
    python scripts/sim_sensor.py --topic reactor2/pump_on --bool --interval 0.5

Variables de entorno equivalentes: MQTT_HOST, MQTT_PORT, SIM_TOPIC, SIM_BASE,
SIM_NOISE, SIM_INTERVAL.
"""

import argparse
import os
import random
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--host",
        default=os.environ.get("MQTT_HOST", "localhost"),
        help="Host del broker MQTT (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MQTT_PORT", "1883")),
        help="Puerto del broker MQTT (default: 1883)",
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("SIM_TOPIC", "reactor1/temperature"),
        help="Topic MQTT del sensor, formato dispositivo/sensor",
    )
    parser.add_argument(
        "--base",
        type=float,
        default=float(os.environ.get("SIM_BASE", "25.0")),
        help="Valor base del sensor (default: 25.0)",
    )
    parser.add_argument(
        "--noise",
        type=float,
        default=float(os.environ.get("SIM_NOISE", "0.5")),
        help="Desviación estándar del ruido gaussiano (default: 0.5)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("SIM_INTERVAL", "1.0")),
        help="Frecuencia de emisión en segundos (default: 1.0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Cantidad de lecturas a emitir; 0 = infinito (default: 0)",
    )
    parser.add_argument(
        "--bool",
        action="store_true",
        help="Emitir valores booleanos (true/false) en lugar de flotantes",
    )
    return parser.parse_args()


def next_value(args):
    if args.bool:
        return "true" if random.random() < 0.5 else "false"
    return f"{args.base + random.gauss(0, args.noise):.2f}"


def main():
    args = parse_args()

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        sys.exit(
            "Falta la librería 'paho-mqtt'. Instalala con: pip install paho-mqtt"
        )

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    tipo = "bool" if args.bool else f"float (±{args.noise})"
    print(f"Publicando en {args.host}:{args.port} topic '{args.topic}' — {tipo}, cada {args.interval}s")
    print("CTRL+C para detener.")

    n = 0
    try:
        while args.count == 0 or n < args.count:
            value = next_value(args)
            client.publish(args.topic, value, qos=0)
            n += 1
            print(f"[{n}] {args.topic}: {value}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulación detenida.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()