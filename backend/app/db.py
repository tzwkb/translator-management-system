"""数据库引擎与 ORM 基类。"""
import json

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase

from .config import DB_URL
from .pending_safety import pending_fingerprint

engine = create_engine(DB_URL)


class Base(DeclarativeBase):
    pass


def ensure_schema():
    columns = {
        "language_pairs": {
            "translation_rate": "NUMERIC(10, 2)",
            "mtpe_rate": "NUMERIC(10, 2)",
            "review_rate": "NUMERIC(10, 2)",
            "lqa_rate": "NUMERIC(10, 2)",
            "lqe_rate": "NUMERIC(10, 2)",
            "currency": "VARCHAR(10)",
            "rate_confirmed_date": "VARCHAR(20)",
        },
        "rate_changes": {
            "source_lang": "VARCHAR(20)",
            "target_lang": "VARCHAR(20)",
        },
        "po_settlements": {
            "source_lang": "VARCHAR(20)",
            "target_lang": "VARCHAR(20)",
        },
        "pending_changes": {
            "idempotency_key": "VARCHAR(160)",
            "request_hash": "VARCHAR(64)",
            "payload_hash": "VARCHAR(64)",
        },
    }
    with engine.begin() as conn:
        existing_tables = set(inspect(conn).get_table_names())
        for table, wanted in columns.items():
            if table not in existing_tables:
                continue
            existing = {c["name"] for c in inspect(conn).get_columns(table)}
            for name, ddl in wanted.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if {"language_pairs", "translators"}.issubset(existing_tables):
            conn.execute(text("""
                UPDATE language_pairs
                SET translation_rate = (SELECT translation_rate FROM translators WHERE translators.id = language_pairs.translator_id)
                WHERE translation_rate IS NULL
            """))
            conn.execute(text("""
                UPDATE language_pairs
                SET mtpe_rate = (SELECT mtpe_rate FROM translators WHERE translators.id = language_pairs.translator_id)
                WHERE mtpe_rate IS NULL
            """))
            conn.execute(text("""
                UPDATE language_pairs
                SET review_rate = (SELECT review_rate FROM translators WHERE translators.id = language_pairs.translator_id)
                WHERE review_rate IS NULL
            """))
            conn.execute(text("""
                UPDATE language_pairs
                SET lqa_rate = (SELECT lqa_rate FROM translators WHERE translators.id = language_pairs.translator_id)
                WHERE lqa_rate IS NULL
            """))
            conn.execute(text("""
                UPDATE language_pairs
                SET currency = (SELECT currency FROM translators WHERE translators.id = language_pairs.translator_id)
                WHERE currency IS NULL
            """))
        if "pending_changes" in existing_tables:
            conn.execute(text("DROP INDEX IF EXISTS ix_pending_active_fingerprint"))
            conn.execute(text("DROP INDEX IF EXISTS ux_pending_active_fingerprint"))
            rows = conn.execute(text("""
                SELECT id, created_by, kind, translator_id, payload, status,
                       idempotency_key, request_hash
                FROM pending_changes ORDER BY id
            """)).mappings().all()
            active_hashes = set()
            idempotency_keys = set()
            for row in rows:
                try:
                    payload = json.loads(row["payload"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    payload = {"raw_payload": row["payload"]}
                fingerprint = pending_fingerprint(row["kind"], row["translator_id"], payload)
                status = row["status"]
                reviewed_by = None
                if status == "pending" and fingerprint in active_hashes:
                    status = "superseded"
                    reviewed_by = "schema-migration"
                elif status == "pending":
                    active_hashes.add(fingerprint)
                key = row["idempotency_key"]
                key_scope = (row["created_by"], key)
                if key and key_scope in idempotency_keys:
                    key = None
                elif key:
                    idempotency_keys.add(key_scope)
                conn.execute(text("""
                    UPDATE pending_changes
                    SET payload_hash=:payload_hash, request_hash=:request_hash,
                        idempotency_key=:idempotency_key,
                        status=:status, reviewed_by=COALESCE(:reviewed_by, reviewed_by)
                    WHERE id=:id
                """), {"payload_hash": fingerprint,
                         "request_hash": row["request_hash"] or fingerprint,
                         "idempotency_key": key,
                         "status": status, "reviewed_by": reviewed_by, "id": row["id"]})
                if key and "pending_idempotency" in existing_tables:
                    migrated_request_hash = row["request_hash"]
                    if not migrated_request_hash or migrated_request_hash == fingerprint:
                        migrated_request_hash = None
                    conn.execute(text("""
                        INSERT OR IGNORE INTO pending_idempotency
                            (created_by, idempotency_key, request_hash, pending_change_id, created_at)
                        VALUES (:created_by, :idempotency_key, :request_hash, :pending_change_id,
                                CURRENT_TIMESTAMP)
                    """), {"created_by": row["created_by"], "idempotency_key": key,
                             "request_hash": migrated_request_hash,
                             "pending_change_id": row["id"]})
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_actor_idempotency
                ON pending_changes(created_by, idempotency_key)
                WHERE idempotency_key IS NOT NULL
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_active_fingerprint
                ON pending_changes(payload_hash)
                WHERE status = 'pending' AND payload_hash IS NOT NULL
            """))
