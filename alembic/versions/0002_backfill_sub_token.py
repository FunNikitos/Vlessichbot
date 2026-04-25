"""backfill users.sub_token for legacy rows

Subscription server (introduced in step 6) routes by ``users.sub_token``.
Pre-existing rows have NULL — they would get 404 on /sub/<token> until
they trigger /newconfig again. This migration generates a stable
``secrets.token_urlsafe(24)`` for every NULL row in one pass.

Idempotent: skips rows that already have a token. Safe to re-run.

Revision ID: 0002_backfill_sub_token
Revises: 0001_initial
Create Date: 2026-04-25
"""
from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "0002_backfill_sub_token"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    rows = bind.execute(
        sa.text("SELECT id FROM users WHERE sub_token IS NULL")
    ).fetchall()

    if not rows:
        return

    # Generate tokens locally — collisions over 24-byte url-safe space are
    # astronomically unlikely, but we still go via the UNIQUE index and
    # retry on the unlikely conflict.
    for (user_id,) in rows:
        for _ in range(5):
            token = secrets.token_urlsafe(24)
            try:
                bind.execute(
                    sa.text(
                        "UPDATE users SET sub_token = :tok "
                        "WHERE id = :uid AND sub_token IS NULL"
                    ),
                    {"tok": token, "uid": user_id},
                )
                break
            except sa.exc.IntegrityError:
                continue


def downgrade() -> None:
    # Не очищаем sub_token: уже разосланные ссылки клиентам должны
    # продолжать работать. Откат — no-op.
    pass
