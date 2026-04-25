"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String, nullable=True),
        sa.Column("first_name", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="new"),
        sa.Column("access_type", sa.String, nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("marzban_username", sa.String, nullable=True),
        sa.Column("marzban_user_id", sa.Integer, nullable=True),
        sa.Column("sub_token", sa.String, nullable=True),
        sa.UniqueConstraint("telegram_id"),
        sa.UniqueConstraint("marzban_username"),
        sa.UniqueConstraint("sub_token"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_sub_token", "users", ["sub_token"])

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String, nullable=False),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer, nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("access_duration_days", sa.Integer, nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"])

    op.create_table(
        "deep_link_invites",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String, nullable=False),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.BigInteger, nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_duration_days", sa.Integer, nullable=False, server_default="30"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_deep_link_invites_token", "deep_link_invites", ["token"])

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("host", sa.String, nullable=False),
        sa.Column("marzban_api_url", sa.String, nullable=False, server_default="http://127.0.0.1:8000"),
        sa.Column("marzban_inbound_tag", sa.String, nullable=False, server_default="VLESS Reality"),
        sa.Column("is_backup", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("load_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("profile_type", sa.String, nullable=False, server_default="standard"),
        sa.Column("routing_mode", sa.String, nullable=False, server_default="smart"),
        sa.Column("subscription_url", sa.Text, nullable=False),
        sa.Column("qr_payload", sa.Text, nullable=False),
        sa.Column("marzban_username", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_connections_user_id", "connections", ["user_id"])

    op.create_table(
        "inbound_state",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("inbound_tag", sa.String, nullable=False),
        sa.Column("current_sni", sa.String, nullable=True),
        sa.Column("current_port", sa.Integer, nullable=True),
        sa.Column("current_short_id", sa.String, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("server_id", "inbound_tag", name="uq_inbound_per_server"),
    )

    op.create_table(
        "sni_donors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("domain", sa.String, nullable=False),
        sa.Column("has_h2", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("has_tls13", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("domain"),
    )

    op.create_table(
        "block_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("servers.id"), nullable=True),
        sa.Column("protocol", sa.String, nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action", sa.String, nullable=True),
    )

    op.create_table(
        "probe_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("servers.id"), nullable=True),
        sa.Column("protocol", sa.String, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("packet_loss", sa.Float, nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("probed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "honeypot_hits",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ip", sa.String, nullable=False),
        sa.Column("country", sa.String, nullable=True),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("hit_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=True),
        sa.Column("event", sa.String, nullable=False),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activity_log_happened_at", "activity_log", ["happened_at"])

    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("section", sa.String, nullable=False, server_default="vpn"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("block_streak", sa.Integer, nullable=False, server_default="0"),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("telegram_id", "section", name="uq_auth_attempt"),
    )

    op.create_table(
        "activation_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_code_id", sa.Integer, sa.ForeignKey("invite_codes.id"), nullable=True),
        sa.Column("deep_link_invite_id", sa.Integer, sa.ForeignKey("deep_link_invites.id"), nullable=True),
        sa.Column("activation_type", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("level", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("user_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_type", sa.String, nullable=False),
        sa.Column("actor_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key"),
    )


def downgrade() -> None:
    for t in [
        "settings",
        "audit_logs",
        "error_logs",
        "activation_logs",
        "auth_attempts",
        "activity_log",
        "honeypot_hits",
        "probe_metrics",
        "block_events",
        "sni_donors",
        "inbound_state",
        "connections",
        "servers",
        "deep_link_invites",
        "invite_codes",
        "users",
    ]:
        op.drop_table(t)
