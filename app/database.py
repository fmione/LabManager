import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import MQTT_HOST, MQTT_PORT

logger = logging.getLogger("labmanager.db")

Base = declarative_base()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://labmanager:labmanager@localhost:5432/labmanager",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    _migrate_schema()
    Base.metadata.create_all(engine)
    _ensure_timescale()


def _migrate_schema():
    with engine.connect() as conn:
        # 1) Renombrar experiment_devices → experiment_sensors si hace falta
        has_exp_devices = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='experiment_devices')"
            )
        ).scalar()
        if has_exp_devices:
            has_exp_sensors = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name='experiment_sensors')"
                )
            ).scalar()
            if not has_exp_sensors:
                conn.execute(text("""
                    CREATE TABLE experiment_sensors (
                        experiment_id INT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                        sensor_id     INT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
                        PRIMARY KEY (experiment_id, sensor_id)
                    )
                """))
            conn.execute(text("""
                INSERT INTO experiment_sensors (experiment_id, sensor_id)
                SELECT ed.experiment_id, s.id
                FROM experiment_devices ed
                JOIN sensors s ON s.device_id = ed.device_id
                WHERE s.device_id IS NOT NULL
                ON CONFLICT DO NOTHING
            """))
            conn.execute(text("DROP TABLE IF EXISTS experiment_devices CASCADE"))
            logger.info("experiment_devices → experiment_sensors migrado.")

        has_devices = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='devices')"
            )
        ).scalar()

        # 2) Migrar sensors: agregar columnas nuevas si no existen
        has_sensor_topic = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name='sensors' AND column_name='mqtt_topic')"
            )
        ).scalar()
        if not has_sensor_topic:
            conn.execute(text("ALTER TABLE sensors ADD COLUMN mqtt_topic VARCHAR(200) DEFAULT ''"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN description VARCHAR(255) DEFAULT ''"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN min_value DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN max_value DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN unit_id INT"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN last_value DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensors ADD COLUMN last_time TIMESTAMPTZ"))
            logger.info("Sensors actualizado: columnas nuevas agregadas.")

        # 3) Migrar sensor.unit (VARCHAR) → tabla units
        has_old_unit_col = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name='sensors' AND column_name='unit')"
            )
        ).scalar()
        if has_old_unit_col:
            units_exist = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name='units')"
                )
            ).scalar()
            if not units_exist:
                conn.execute(text("""
                    CREATE TABLE units (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(80) UNIQUE NOT NULL,
                        symbol VARCHAR(20) NOT NULL,
                        category VARCHAR(30) NOT NULL DEFAULT 'otra'
                    )
                """))
            conn.execute(text("""
                INSERT INTO units (name, symbol, category)
                SELECT DISTINCT unit::text, unit::text, 'otra'
                FROM sensors WHERE unit IS NOT NULL AND unit <> ''
                ON CONFLICT (name) DO NOTHING
            """))
            conn.execute(text("""
                UPDATE sensors s SET unit_id = u.id
                FROM units u WHERE s.unit = u.symbol AND s.unit_id IS NULL
            """))
            conn.execute(text("ALTER TABLE sensors DROP COLUMN unit"))
            logger.info("Unidades migradas a la tabla units.")

        # 4) Migrar mqtt_topic desde devices si aún quedan con topic vacío
        if has_devices:
            has_device_id = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='sensors' AND column_name='device_id')"
                )
            ).scalar()
            if has_device_id:
                conn.execute(text(
                    "UPDATE sensors AS s SET mqtt_topic = d.name || '/' || s.name "
                    "FROM devices d WHERE s.device_id = d.id AND s.mqtt_topic = ''"
                ))
                conn.execute(text("ALTER TABLE sensors DROP COLUMN device_id"))
                logger.info("mqtt_topic poblado desde devices; device_id eliminado.")
            conn.execute(text("DROP TABLE IF EXISTS devices CASCADE"))
            logger.info("Tabla devices eliminada.")

        # 5) experiment_sensors si faltara
        has_exp_sensors_t = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='experiment_sensors')"
            )
        ).scalar()
        if not has_exp_sensors_t:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS experiment_sensors (
                    experiment_id INT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                    sensor_id     INT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
                    PRIMARY KEY (experiment_id, sensor_id)
                )
            """))

        # 6) start_time/end_time en experiments
        has_start = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name='experiments' AND column_name='start_time')"
            )
        ).scalar()
        if not has_start:
            conn.execute(text("ALTER TABLE experiments ADD COLUMN start_time TIMESTAMPTZ"))
            conn.execute(text("ALTER TABLE experiments ADD COLUMN end_time TIMESTAMPTZ"))

        # 7) Tabla units
        has_units = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='units')"
            )
        ).scalar()
        if not has_units:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS units (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(80) UNIQUE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    category VARCHAR(30) NOT NULL DEFAULT 'otra'
                )
            """))
            logger.info("Tabla units creada.")

        # 8) Tabla settings (key/value: timezone, MQTT...)
        has_settings = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='settings')"
            )
        ).scalar()
        if not has_settings:
            conn.execute(text("""
                CREATE TABLE settings (
                    key   VARCHAR(50) PRIMARY KEY,
                    value VARCHAR(255) NOT NULL
                )
            """))
            logger.info("Tabla settings creada.")

        def seed_default(k, v):
            exists = conn.execute(
                text("SELECT 1 FROM settings WHERE key = :k"),
                {"k": k},
            ).scalar()
            if not exists:
                conn.execute(
                    text("INSERT INTO settings (key, value) VALUES (:k, :v)"),
                    {"k": k, "v": v},
                )

        seed_default("timezone", "Etc/GMT+3")
        seed_default("mqtt_host", MQTT_HOST)
        seed_default("mqtt_port", str(MQTT_PORT))
        logger.info("Settings iniciales aseguradas.")

        # Migrar timezone legacy (IANA country zones → Etc/GMT offset fijo)
        from datetime import datetime as _dt, timezone as _tz
        from zoneinfo import ZoneInfo as _ZI
        row = conn.execute(
            text("SELECT value FROM settings WHERE key = 'timezone'")
        ).scalar()
        if row and not row.startswith("Etc/GMT"):
            try:
                offset = _dt.now(_tz.utc).astimezone(_ZI(row)).utcoffset().total_seconds()
                h = int(offset // 3600)
                conn.execute(
                    text("UPDATE settings SET value = :v WHERE key = 'timezone'"),
                    {"v": f"Etc/GMT{-h:+d}"},
                )
                logger.info("Timezone migrado de %s a Etc/GMT%s.", row, f"{-h:+d}")
            except Exception:
                logger.debug("No se pudo migrar timezone '%s', se mantiene.", row)

        conn.commit()


def _ensure_timescale():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        exists = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='sensor_data')"
            )
        ).scalar()
        if exists:
            is_hyp = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name='sensor_data')"
                )
            ).scalar()
            if not is_hyp:
                conn.execute(text("SELECT create_hypertable('sensor_data', 'time')"))
                logger.info("Hypertable 'sensor_data' creada.")
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_time "
            "ON sensor_data (sensor_id, time DESC)"
        ))
        conn.commit()