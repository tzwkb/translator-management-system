"""Pending-change dry-run and idempotency tests."""
import tempfile
import threading
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

from app import db, services
from app.models import AuditLog, Base, PO, PendingChange, Translator
from app.routers import po as po_router
from app.services import (find_idempotent_request, make_pending,
                          needs_legacy_replay_validation, pending_request_hash,
                          prepare_po)


def new_session(tmpdir):
    engine = create_engine(f"sqlite:///{Path(tmpdir) / 'pending.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def check_schema_upgrade(tmpdir):
    upgrade_engine = create_engine(f"sqlite:///{Path(tmpdir) / 'upgrade.db'}")
    with upgrade_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE pending_changes (
                id INTEGER PRIMARY KEY,
                created_by VARCHAR(50),
                kind VARCHAR(30),
                translator_id INTEGER,
                payload TEXT,
                idempotency_key VARCHAR(160),
                payload_hash VARCHAR(64),
                status VARCHAR(20),
                reviewed_by VARCHAR(50),
                created_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO pending_changes
                (id, created_by, kind, translator_id, payload, idempotency_key,
                 payload_hash, status)
            VALUES
                (1, '资源端Agent', 'rate_change', 1, :payload,
                 'legacy-key', 'legacy-hash', 'pending')
        """), {"payload": '{"source_lang":"zh","target_lang":"en","new_rate":180}'})
        conn.execute(text("""
            INSERT INTO pending_changes
                (id, created_by, kind, translator_id, payload, idempotency_key,
                 payload_hash, status)
            VALUES
                (2, '资源端Agent', 'rate_change', 1, :payload,
                 'legacy-conflict', 'legacy-conflict-hash', 'pending')
        """), {"payload": '{"source_lang":"ZH","target_lang":"EN","new_rate":181}'})
        conn.execute(text("""
            INSERT INTO pending_changes
                (id, created_by, kind, translator_id, payload, idempotency_key,
                 payload_hash, status)
            VALUES
                (3, '资源端Agent', 'po', 1, :payload,
                 'legacy-approved-po', 'legacy-approved-hash', 'approved')
        """), {"payload": '{"translator_id":1,"settlement_month":"2026-12",'
                            '"source_lang":null,"target_lang":null,"role":"翻译",'
                            '"word_count":1000,"rate":180,"currency":"CNY",'
                            '"status":"未开票","po_number":"LEGACY-PO"}'})
    Base.metadata.create_all(upgrade_engine)
    with Session(upgrade_engine) as session:
        session.add(Translator(id=1, name="旧版译员", native_language="中文",
                               onboarding_date="2026-01-01"))
        session.add(PO(translator_id=1, settlement_month="2026-12", role="翻译",
                       word_count=1000, rate=180, amount=180, currency="CNY",
                       status="未开票", po_number="LEGACY-PO"))
        session.commit()
    original_engine = db.engine
    db.engine = upgrade_engine
    try:
        db.prepare_legacy_schema_for_baseline()
    finally:
        db.engine = original_engine
    inspector = inspect(upgrade_engine)
    columns = {item["name"] for item in inspector.get_columns("pending_changes")}
    indexes = {item["name"] for item in inspector.get_indexes("pending_changes")}
    assert {"idempotency_key", "request_hash", "payload_hash"}.issubset(columns)
    assert {
        "ix_pending_changes_payload_hash",
        "ux_pending_actor_idempotency",
        "ux_pending_active_fingerprint",
    }.issubset(indexes)
    assert "pending_idempotency" in inspector.get_table_names()
    request_payload = {"source_lang": "ZH", "target_lang": "EN", "new_rate": 180}
    request_hash = pending_request_hash("rate_change", 1, request_payload)
    with Session(upgrade_engine) as session:
        replay = find_idempotent_request(session, "资源端Agent", "legacy-key", request_hash)
        assert replay is None
        same_content = make_pending(
            session, "资源端Agent", "rate_change", 1, request_payload,
            idempotency_key="legacy-second-key",
            request_hash=pending_request_hash("rate_change", 1, request_payload),
        )
        assert same_content["pending_id"] == 1
        try:
            make_pending(
                session, "资源端Agent", "rate_change", 1,
                {"source_lang": "ZH", "target_lang": "EN", "new_rate": 999},
                idempotency_key="legacy-conflict",
                request_hash=pending_request_hash(
                    "rate_change", 1,
                    {"source_lang": "ZH", "target_lang": "EN", "new_rate": 999},
                ),
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("legacy key with different content must return 409")

        stored_hash = session.get(PendingChange, 1).payload_hash
        session.execute(text("""
            INSERT INTO pending_idempotency
                (created_by, idempotency_key, request_hash, pending_change_id, created_at)
            VALUES ('资源端Agent', 'legacy-race', NULL, 1, CURRENT_TIMESTAMP)
        """))
        session.commit()

    barrier = threading.Barrier(2)
    results, errors = [], []

    def claim_legacy(request_hash_value):
        try:
            barrier.wait(timeout=2)
            with Session(upgrade_engine) as session:
                result = find_idempotent_request(
                    session, "资源端Agent", "legacy-race", request_hash_value,
                    candidate_payload_hash=stored_hash,
                )
                results.append(result)
        except HTTPException as exc:
            errors.append(exc.status_code)

    threads = [threading.Thread(target=claim_legacy, args=(value,))
               for value in ("request-a", "request-b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert len(results) == 1, (results, errors)
    assert errors == [409], errors

    legacy_po_request = {
        "translator_id": 1, "settlement_month": "2026-12", "source_lang": None,
        "target_lang": None, "role": "翻译", "word_count": 1000, "rate": 180,
        "currency": "CNY", "status": "未开票", "po_number": "LEGACY-PO",
    }
    with Session(upgrade_engine) as session:
        assert needs_legacy_replay_validation(
            session, "资源端Agent", "legacy-approved-po",
        ) is True
        prepared = prepare_po(session, legacy_po_request, check_duplicate=False)
        replay = make_pending(
            session, "资源端Agent", "po", 1, prepared,
            idempotency_key="legacy-approved-po",
            request_hash=pending_request_hash("po", 1, legacy_po_request),
        )
        assert replay["pending_id"] == 3
        assert replay["status"] == "approved"


def check_concurrent_pending(tmpdir, keys):
    engine = create_engine(f"sqlite:///{Path(tmpdir) / ('concurrent-' + keys[0][-2:] + '.db')}")
    Base.metadata.create_all(engine)
    original_engine = db.engine
    db.engine = engine
    try:
        db.prepare_legacy_schema_for_baseline()
    finally:
        db.engine = original_engine
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker(key):
        try:
            barrier.wait(timeout=2)
            with Session(engine) as session:
                results.append(make_pending(
                    session, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                    idempotency_key=key,
                ))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(key,)) for key in keys]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    with Session(engine) as session:
        rows = session.scalars(select(PendingChange).where(PendingChange.status == "pending")).all()
    assert not errors, errors
    assert len(rows) == 1
    assert len(results) == 2
    assert {item["pending_id"] for item in results} == {rows[0].id}


def check_atomic_approval(tmpdir):
    engine = create_engine(f"sqlite:///{Path(tmpdir) / 'approval.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        translator = Translator(name="并发审批", native_language="中文", onboarding_date="2026-07-01")
        session.add(translator)
        session.flush()
        pending = PendingChange(
            created_by="资源端Agent", kind="po", translator_id=translator.id,
            payload='{"translator_id": 1, "settlement_month": "2026-11", "word_count": 1000}',
            payload_hash="approval-test", status="pending",
        )
        session.add(pending)
        session.commit()
        pending_id = pending.id

    barrier = threading.Barrier(2)
    original_engine = po_router.engine
    original_create = po_router.svc_create_po
    results, errors = [], []

    def synced_create(*args, **kwargs):
        try:
            barrier.wait(timeout=1)
        except threading.BrokenBarrierError:
            pass
        return original_create(*args, **kwargs)

    def worker():
        try:
            results.append(po_router.approve_pending(pending_id, "资源端"))
        except HTTPException as exc:
            errors.append(exc.status_code)
        except Exception as exc:
            errors.append(type(exc).__name__)

    po_router.engine = engine
    po_router.svc_create_po = synced_create
    try:
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
    finally:
        po_router.engine = original_engine
        po_router.svc_create_po = original_create

    with Session(engine) as session:
        po_count = count(session, PO)
    assert len(results) == 1, (results, errors)
    assert errors == [404], errors
    assert po_count == 1


def main():
    with tempfile.TemporaryDirectory(prefix="pending-idempotency-") as tmpdir:
        check_schema_upgrade(tmpdir)
        with new_session(tmpdir) as s:
            preview = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m1:po", dry_run=True,
            )
            assert preview["dry_run"] is True
            assert count(s, PendingChange) == 0
            assert count(s, AuditLog) == 0

            first = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m1:po",
            )
            retry = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m1:po",
            )
            assert retry["pending_id"] == first["pending_id"]
            assert retry["deduplicated"] is True
            assert count(s, PendingChange) == 1

            try:
                make_pending(
                    s, "资源端Agent", "po", 1, {"settlement_month": "2026-08"},
                    idempotency_key="wechat:c1:m1:po",
                )
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("same key with different payload must return 409")

            content_retry = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m2:po",
            )
            assert content_retry["pending_id"] == first["pending_id"]
            assert content_retry["deduplicated"] is True
            assert count(s, PendingChange) == 1

            existing = s.get(PendingChange, first["pending_id"])
            existing.status = "rejected"
            s.commit()
            second_key_retry = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m2:po",
            )
            assert second_key_retry["pending_id"] == first["pending_id"]
            assert second_key_retry["status"] == "rejected"
            assert count(s, PendingChange) == 1
            resubmitted = make_pending(
                s, "资源端Agent", "po", 1, {"settlement_month": "2026-07"},
                idempotency_key="wechat:c1:m3:po",
            )
            assert resubmitted["pending_id"] != first["pending_id"]
            assert resubmitted["deduplicated"] is False
            assert count(s, PendingChange) == 2

        check_concurrent_pending(tmpdir, ["wechat:c1:a1:po", "wechat:c1:a1:po"])
        check_concurrent_pending(tmpdir, ["wechat:c1:b1:po", "wechat:c1:b2:po"])
        check_atomic_approval(tmpdir)

    print("pending dry-run and idempotency behavior passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
