"""All ORM models — single source of truth for the schema.

Каждая таблица описана подробно с указанием бизнес-смысла поля.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ----------------------- Users / Access -----------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # status: new | active | expired | blocked
    status: Mapped[str] = mapped_column(String, default="new", nullable=False)
    access_type: Mapped[str | None] = mapped_column(String, nullable=True)  # trial | code | manual
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Marzban-side identity
    marzban_username: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    marzban_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Personal subscription token used in /sub/<token> (наш aiohttp-сервер)
    sub_token: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    connections: Mapped[list[Connection]] = relationship(back_populates="user")


class InviteCode(Base):
    """4-значные / текстовые инвайт-коды (вводятся вручную)."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    access_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)


class DeepLinkInvite(Base):
    """Одноразовые deep-link инвайты вида t.me/bot?start=inv_xxx."""

    __tablename__ = "deep_link_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_duration_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


# ----------------------- VPN-side -----------------------


class Server(Base):
    """Один или несколько VPS-нод. Сейчас — обычно один primary.
    Поле marzban_inbound_tag — основной inbound на этой ноде."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    marzban_api_url: Mapped[str] = mapped_column(String, default="http://127.0.0.1:8000", nullable=False)
    marzban_inbound_tag: Mapped[str] = mapped_column(String, default="VLESS Reality", nullable=False)

    is_backup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # active | down | disabled
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    load_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Connection(Base):
    """Один логический «конфиг» пользователя. Ссылка/QR — это копия
    subscription-URL'а Marzban; имя — для отображения в боте."""

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)
    profile_type: Mapped[str] = mapped_column(String, default="standard", nullable=False)
    # 'full' | 'smart' (split-tunnel)
    routing_mode: Mapped[str] = mapped_column(String, default="smart", nullable=False)

    subscription_url: Mapped[str] = mapped_column(Text, nullable=False)
    qr_payload: Mapped[str] = mapped_column(Text, nullable=False)
    marzban_username: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="connections")
    server: Mapped[Server] = relationship()


class InboundState(Base):
    """Текущее состояние Marzban-inbound: SNI/порт/short_id, чтобы
    бот понимал, что менять при ротации, и подсвечивал в /status."""

    __tablename__ = "inbound_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False)
    inbound_tag: Mapped[str] = mapped_column(String, nullable=False)
    current_sni: Mapped[str | None] = mapped_column(String, nullable=True)
    current_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_short_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("server_id", "inbound_tag", name="uq_inbound_per_server"),)


class SniDonor(Base):
    """Список доменов-кандидатов на роль SNI для Reality.
    Заполняется reality_sni_finder, чтобы не маскироваться под IP, не
    принадлежащий нашему хостеру."""

    __tablename__ = "sni_donors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    has_h2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_tls13: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ----------------------- Monitoring -----------------------


class BlockEvent(Base):
    __tablename__ = "block_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id"), nullable=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action: Mapped[str | None] = mapped_column(String, nullable=True)


class ProbeMetric(Base):
    __tablename__ = "probe_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id"), nullable=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packet_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    probed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HoneypotHit(Base):
    __tablename__ = "honeypot_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event: Mapped[str] = mapped_column(String, nullable=False)
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


# ----------------------- Auth / Antispam -----------------------


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section: Mapped[str] = mapped_column(String, default="vpn", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    block_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("telegram_id", "section", name="uq_auth_attempt"),)


# ----------------------- Operational -----------------------


class ActivationLog(Base):
    __tablename__ = "activation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    invite_code_id: Mapped[int | None] = mapped_column(ForeignKey("invite_codes.id"), nullable=True)
    deep_link_invite_id: Mapped[int | None] = mapped_column(
        ForeignKey("deep_link_invites.id"), nullable=True
    )
    activation_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
