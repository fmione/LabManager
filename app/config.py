import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://labmanager:labmanager@localhost:5432/labmanager",
)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC_FILTER = os.environ.get("MQTT_TOPIC_FILTER", "#")

SECRET_KEY = os.environ.get("SECRET_KEY", "clave-desarrollo-cambiar")
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "86400"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lab.local")

APP_NAME = "LabManager"
