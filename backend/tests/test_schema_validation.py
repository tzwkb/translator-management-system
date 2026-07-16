"""请求体格式校验回归测试。"""

from pydantic import ValidationError

from app.schemas import (CapacityIn, ComplaintIn, ContractIn, LanguagePairIn,
                         POIn, QualityIn, RateChangeIn, TranslatorIn)


def rejects(model, **data):
    try:
        model(**data)
    except ValidationError:
        return True
    return False


def main():
    checks = [
        ("译员入库日期必须是真实日期", rejects(TranslatorIn, name="X", native_language="中文", onboarding_date="2025-01-32")),
        ("译员邮箱格式非法应拒绝", rejects(TranslatorIn, name="X", native_language="中文", onboarding_date="2025-01-01", email="bad-email")),
        ("译员准时率不能超过100", rejects(TranslatorIn, name="X", native_language="中文", onboarding_date="2025-01-01", punctuality_rate=101)),
        ("报价变更日期必须是真实日期", rejects(RateChangeIn, change_date="2026-13-01")),
        ("报价变更新费率不能为负", rejects(RateChangeIn, change_date="2026-06-01", new_rate=-1)),
        ("PO结算月必须是真实月份", rejects(POIn, translator_id=1, settlement_month="2026-13")),
        ("PO字数不能为负", rejects(POIn, translator_id=1, settlement_month="2026-06", word_count=-1)),
        ("语言对费率不能为负", rejects(LanguagePairIn, source_lang="ZH", target_lang="EN", translation_rate=-1)),
        ("合同日期必须是真实日期", rejects(ContractIn, sign_date="2026-02-30")),
        ("质量周期必须是真实月份", rejects(QualityIn, evaluation_period="2026-00")),
        ("质量分不能超过100", rejects(QualityIn, score=101)),
        ("客诉日期必须是真实日期", rejects(ComplaintIn, date="2026-04-31")),
        ("产能月份必须在1-12", rejects(CapacityIn, period_year=2026, period_month=13, week_no=1)),
        ("产能周次必须在1-6", rejects(CapacityIn, period_year=2026, period_month=6, week_no=0)),
        ("产能占用必须在0-100", rejects(CapacityIn, period_year=2026, period_month=6, week_no=1, occupancy_pct=101)),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("失败:", "；".join(failed))
        return 1
    print("schema format validation rejects invalid values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
