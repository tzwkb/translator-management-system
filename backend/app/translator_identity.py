"""译员稳定 ID 与可变名称之间的映射规则。"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Translator, TranslatorAlias


def normalize_translator_name(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def assert_name_not_reserved(
    session: Session,
    name: str,
    translator_id: int | None = None,
):
    normalized = normalize_translator_name(name)
    if not normalized:
        raise ValueError("译员姓名不能为空")
    alias = session.scalar(
        select(TranslatorAlias).where(
            TranslatorAlias.normalized_alias == normalized,
            TranslatorAlias.translator_id != translator_id,
        )
    )
    if alias:
        raise ValueError("该姓名已作为其他译员的名称映射")


def add_translator_alias(
    session: Session,
    translator_id: int,
    alias: str,
) -> tuple[TranslatorAlias | None, bool]:
    normalized = normalize_translator_name(alias)
    if not normalized:
        raise ValueError("名称映射不能为空")
    translator = session.get(Translator, translator_id)
    if not translator or translator.deleted_at:
        raise ValueError("译员不存在")
    if normalize_translator_name(translator.name) == normalized:
        return None, False
    canonical_matches = [
        row
        for row in session.scalars(
            select(Translator).where(
                Translator.deleted_at.is_(None),
                Translator.id != translator_id,
            )
        ).all()
        if normalize_translator_name(row.name) == normalized
    ]
    if canonical_matches:
        raise ValueError("该名称与其他译员的当前姓名重复")
    existing = session.scalar(
        select(TranslatorAlias).where(
            TranslatorAlias.normalized_alias == normalized,
        )
    )
    if existing:
        if existing.translator_id == translator_id:
            return existing, False
        raise ValueError("该名称已映射到其他译员")
    row = TranslatorAlias(
        translator_id=translator_id,
        alias=str(alias).strip(),
        normalized_alias=normalized,
    )
    session.add(row)
    session.flush()
    return row, True


def exact_translator_ids_for_name(session: Session, name: str) -> set[int]:
    normalized = normalize_translator_name(name)
    if not normalized:
        return set()
    rows = session.scalars(
        select(Translator).where(Translator.deleted_at.is_(None))
    ).all()
    result = {
        row.id
        for row in rows
        if normalize_translator_name(row.name) == normalized
    }
    result.update(
        session.scalars(
            select(TranslatorAlias.translator_id)
            .join(Translator, Translator.id == TranslatorAlias.translator_id)
            .where(
                TranslatorAlias.normalized_alias == normalized,
                Translator.deleted_at.is_(None),
            )
        ).all()
    )
    return result


def fuzzy_translator_ids_for_name(session: Session, name: str) -> set[int]:
    normalized = normalize_translator_name(name)
    if not normalized:
        return set()
    result = set()
    for row in session.scalars(
        select(Translator).where(Translator.deleted_at.is_(None))
    ).all():
        candidate = normalize_translator_name(row.name)
        if candidate and (candidate in normalized or normalized in candidate):
            result.add(row.id)
    for alias in session.scalars(
        select(TranslatorAlias)
        .join(Translator, Translator.id == TranslatorAlias.translator_id)
        .where(Translator.deleted_at.is_(None))
    ).all():
        candidate = alias.normalized_alias
        if candidate and (candidate in normalized or normalized in candidate):
            result.add(alias.translator_id)
    return result
