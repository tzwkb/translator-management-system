"""请求体格式校验回归测试。"""

from pydantic import ValidationError

from app.schemas import (CapacityOverrideIn, ComplaintIn, ContractIn, LanguagePairIn,
                         POIn, PaymentAccountIn, ProjectExperienceIn,
                         ProjectPriceIn, QualityIn, RateChangeIn, TranslatorIn)


def rejects(model, **data):
    try:
        model(**data)
    except ValidationError:
        return True
    return False


def main():
    base_translator = {
        "name": "X",
        "native_language": "中文",
        "onboarding_date": "2025-01-01",
        "gender": "female",
    }
    checks = [
        ("译员入库日期必须是真实日期", rejects(TranslatorIn, **(base_translator | {"onboarding_date": "2025-01-32"}))),
        ("译员邮箱格式非法应拒绝", rejects(TranslatorIn, **(base_translator | {"email": "bad-email"}))),
        ("译员准时率不能超过100", rejects(TranslatorIn, **(base_translator | {"punctuality_rate": 101}))),
        ("译员性别必填", rejects(TranslatorIn, name="X", native_language="中文", onboarding_date="2025-01-01")),
        ("译员性别必须使用固定枚举", rejects(TranslatorIn, **(base_translator | {"gender": "unknown"}))),
        ("译员主体类型必须使用固定枚举", rejects(TranslatorIn, **(base_translator | {"entity_type": "company"}))),
        ("译员结算策略必须使用固定枚举", rejects(TranslatorIn, **(base_translator | {"settlement_mode": "weekly"}))),
        ("旧档期字段不得被静默忽略", rejects(TranslatorIn, **(base_translator | {"availability": "空闲"}))),
        ("旧双休字段不得被静默忽略", rejects(TranslatorIn, **(base_translator | {"weekend_off": True}))),
        ("项目经历项目名不能为空", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="  ")),
        ("项目经历合作来源必须使用固定枚举", rejects(ProjectExperienceIn, cooperation_source="partner", project_status="current", project_name="X")),
        ("项目经历状态必须使用固定枚举", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="active", project_name="X")),
        ("项目经历剩余量不能为负", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", remaining_volume=-1)),
        ("项目经历语言对必须同时填写", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", source_lang="ZH")),
        ("项目经历日期必须是真实日期", rejects(ProjectExperienceIn, cooperation_source="external", project_status="past", project_name="X", start_date="2026-02-30")),
        ("当前项目必须填剩余字数", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", start_date="2026-08-01", deadline="2026-08-31")),
        ("当前项目必须填开始日期", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", remaining_volume=1000, deadline="2026-08-31")),
        ("当前项目必须填截止或结束日期", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", remaining_volume=1000, start_date="2026-08-01")),
        ("当前项目截止日不能早于开始日", rejects(ProjectExperienceIn, cooperation_source="our_company", project_status="current", project_name="X", remaining_volume=1000, start_date="2026-08-31", deadline="2026-08-01")),
        ("报价变更日期必须是真实日期", rejects(RateChangeIn, change_date="2026-13-01")),
        ("报价变更新费率不能为负", rejects(RateChangeIn, change_date="2026-06-01", new_rate=-1)),
        ("PO结算月必须是真实月份", rejects(POIn, translator_id=1, settlement_month="2026-13")),
        ("PO字数不能为负", rejects(POIn, translator_id=1, settlement_month="2026-06", word_count=-1)),
        ("手工PO必须填写金额", rejects(POIn, translator_id=1, settlement_month="2026-06", pricing_mode="manual")),
        ("语言对费率不能为负", rejects(LanguagePairIn, source_lang="ZH", target_lang="EN", translation_rate=-1)),
        ("翻译项目价格应自动绑定翻译任务", ProjectPriceIn(project_name="X", price_type="translation", amount=100, unit="per_1000", currency="CNY").task_type == "翻译"),
        ("审校项目价格应自动绑定审校任务", ProjectPriceIn(project_name="X", price_type="review", amount=80, unit="per_1000", currency="CNY").task_type == "审校"),
        ("其他价格必须填写自定义任务名", rejects(ProjectPriceIn, project_name="X", price_type="custom", amount=1, unit="other", currency="CNY")),
        ("一口价单位只能为项目或任务", rejects(ProjectPriceIn, project_name="X", price_type="fixed", amount=1, unit="hour", currency="CNY")),
        ("对公美元币种必须为USD", rejects(PaymentAccountIn, method="corporate_usd", currency="CNY", account_name="X")),
        ("合同日期必须是真实日期", rejects(ContractIn, sign_date="2026-02-30")),
        ("质量周期必须是真实月份", rejects(QualityIn, evaluation_period="2026-00")),
        ("质量分不能超过100", rejects(QualityIn, score=101)),
        ("客诉日期必须是真实日期", rejects(ComplaintIn, date="2026-04-31")),
        ("月度产能修正状态必须使用四档枚举", rejects(CapacityOverrideIn, status="满负荷", reason="测试")),
        ("月度产能修正必须填写原因", rejects(CapacityOverrideIn, status="健康", reason="  ")),
        ("月度产能修正不接受旧占用百分比", rejects(CapacityOverrideIn, status="健康", reason="测试", occupancy_pct=50)),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("失败:", "；".join(failed))
        return 1
    print("schema format validation rejects invalid values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
