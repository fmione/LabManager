# LabManager

Monitoreo de sensores IoT de laboratorio (temperatura, pH, OD, turbidez, etc.).
Los sensores publican por MQTT en el topic `dispositivo/sensor` el valor crudo
(`25.3`, `true`, `0.4`, etc.) y un servicio ingestor lo almacena en
PostgreSQL + TimescaleDB. La web (FastAPI + Jinja2 + Bootstrap) permite
administrar experimentos/dispositivos/sensores y visualizar series temporales.

## Stack

- **FastAPI** (Python 3.12) + Jinja2 + Bootstrap 5 + Chart.js
- **TimescaleDB** (PostgreSQL) — tabla `sensor_data` como hypertable
- **Eclipse Mosquitto** (MQTT broker)
- Todo orquestado con **Docker Compose**

## Roles de usuario

| Rol           | Permisos                                                        |
|---------------|-----------------------------------------------------------------|
| Administrador | Todo + gestionar usuarios (crear, desactivar, reset, eliminar)  |
| Jefe de Laboratorio | Crear/eliminar experimentos, dispositivos y sensores, ver datos |
| Invitado            | Solo visualizar datos y gráficos                                |

El usuario administrador inicial se crea automáticamente al primer arranque con
las variables `ADMIN_USERNAME` y `ADMIN_PASSWORD` del archivo `.env`.

## Puesta en marcha

```bash
cp .env.example .env   # o editar el .env existente
docker compose up --build
```

La web queda en <http://localhost:8082>.

## Configuración

Las variables relevantes están en `.env`:

- `POSTGRES_USER/PASSWORD/DB`, `POSTGRES_PORT`
- `MQTT_PORT`, `MQTT_TOPIC_FILTER` (por defecto `#`, suscribe a todos los topics)
- `SECRET_KEY`, `SESSION_MAX_AGE`
- `ADMIN_USERNAME/PASSWORD/EMAIL`

## Cómo reciben datos los sensores

1. Se registra el dispositivo en la web (con su experimento) y se agregan sensores.
2. El sensor publica el **valor crudo** en `dispositivo/sensor`:
   - `fermentador1/temperature` → `25.3`
   - `reactor2/pump_on` → `true`
3. El ingestor MQTT valida que `dispositivo/sensor` exista y esté activo; si no,
   ignora el mensaje (el registro es manual a propósito).

## Prueba rápida del ingestor MQTT

Publicá un mensaje de prueba (requiere `mosquitto_pub` en tu máquina):

```bash
# crear un experimento "Bio1", un dispositivo "reactor1" con sensor "temperature"
# luego:
mosquitto_pub -h localhost -p 1883 -t reactor1/temperature -m 25.3
mosquitto_pub -h localhost -p 1883 -t reactor1/pump_on -m true
```

Luego entrás a la web → **Datos y gráficos** y seleccionás el sensor.

## Estructura

```
app/
├── main.py               # app FastAPI, dashboard, startup (DB + admin + MQTT)
├── config.py             # configuración por variables de entorno
├── database.py           # motor SQLAlchemy + init (TimescaleDB hypertable)
├── models.py             # ORM: users, experiments, devices, sensors, sensor_data
├── auth.py               # hashing de contraseñas y sesión firmada
├── web.py                # helpers de sesión/render/redirect
├── mqtt.py               # servicio ingestor MQTT (paho) en thread
├── routers/              # auth, usuarios, experimentos, dispositivos, datos
├── templates/            # plantillas Jinja2
└── static/               # Bootstrap 5, Chart.js, icons (offline)
mosquitto/config/         # configuración del broker
```

## Notas de seguridad

- El broker Mosquitto arranca con `allow_anonymous true` (entorno de laboratorio).
  Para producción, configurá `password_file` y `require_authentication` en
  `mosquitto/config/mosquitto.conf`.
- Cambiá `SECRET_KEY`, `ADMIN_PASSWORD` y `POSTGRES_PASSWORD` en producción.
