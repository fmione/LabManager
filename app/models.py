from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Setting(Base):
    """Par clave/valor para configuración de la app (zona horaria, MQTT...)."""

    __tablename__ = "settings"

    key = Column(String(50), primary_key=True)
    value = Column(String(255), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="lector")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    symbol = Column(String(20), nullable=False)
    category = Column(String(30), nullable=False, default="otra")

    sensors = relationship("Sensor", back_populates="unit")


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    description = Column(String(255), default="")
    mqtt_topic = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    data_type = Column(String(10), default="float")
    last_value = Column(Float, nullable=True)
    last_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    unit = relationship("Unit", back_populates="sensors")
    experiments = relationship(
        "Experiment", secondary="experiment_sensors", back_populates="sensors"
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, default="")
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    sensors = relationship(
        "Sensor", secondary="experiment_sensors", back_populates="experiments"
    )
    notes = relationship(
        "Note",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by=lambda: Note.created_at.desc(),
    )


class ExperimentSensor(Base):
    __tablename__ = "experiment_sensors"
    __table_args__ = (
        UniqueConstraint("experiment_id", "sensor_id", name="uq_exp_sensor"),
    )

    experiment_id = Column(
        Integer, ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )
    sensor_id = Column(
        Integer, ForeignKey("sensors.id", ondelete="CASCADE"), primary_key=True
    )


class SensorData(Base):
    """Registros telemétricos. Hypertable particionada por `time`."""

    __tablename__ = "sensor_data"
    __table_args__ = (PrimaryKeyConstraint("time", "sensor_id"),)

    time = Column(DateTime(timezone=True), nullable=False)
    sensor_id = Column(
        Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False
    )
    value = Column(Float, nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(
        Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    experiment = relationship("Experiment", back_populates="notes")
    user = relationship("User")
    images = relationship(
        "NoteImage",
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="NoteImage.id",
    )


class NoteImage(Base):
    __tablename__ = "note_images"

    id = Column(Integer, primary_key=True)
    note_id = Column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    data = Column(LargeBinary, nullable=False)
    content_type = Column(String(30), nullable=False)
    filename = Column(String(255), default="")

    note = relationship("Note", back_populates="images")
