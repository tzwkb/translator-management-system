"""首次启动写入的示例数据（库空时才写）。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import engine
from .models import (PO, Capacity, Complaint, Contract, LanguagePair,
                     PaymentAccount, PaymentInfo, ProjectPrice, QualityScore,
                     RateChange, Translator,
                     TranslatorProjectExperience)
from .security import enc
from .services import resync_quality_summary, resync_translator


def seed():
    with Session(engine) as s:
        if s.scalar(select(func.count()).select_from(Translator)):
            for tid in s.scalars(select(Translator.id)).all():
                resync_quality_summary(s, tid)
            s.commit()
            return
        ts = [
            Translator(name="张明", wechat="zhangming_wx", email="zm@example.com",
                       native_language="中文", onboarding_date="2025-01-01", source="推荐",
                       gender="male", entity_type="individual",
                       translation_rate=180, mtpe_rate=120, review_rate=90, status="Active",
                       current_project="燕云", role="翻译", availability="健康",
                       domains="RPG,SLG", cat_tools="Trados,memoQ", currency="CNY", payment_method="银行转账",
                       contract_status="有效", contract_expiry="2026-12-31", nda_signed=True,
                       responsiveness="快", cooperation_rating="优先合作", punctuality_rate=98,
                       last_contact="2026-06-20"),
            Translator(name="李娜", wechat="lina_t", email="lina@example.com",
                       native_language="中文", onboarding_date="2024-09-15", source="平台",
                       gender="female", entity_type="individual",
                       translation_rate=220, lqa_rate=80, status="Active",
                       current_project="洛克王国", role="翻译", availability="饱和", domains="二次元,卡牌",
                       cat_tools="memoQ", currency="CNY", payment_method="支付宝", contract_status="有效",
                       contract_expiry="2026-09-15", nda_signed=True, responsiveness="快",
                       cooperation_rating="优先合作", punctuality_rate=95, last_contact="2026-06-24"),
            Translator(name="王伟", email="ww@example.com", translation_rate=150,
                       native_language="中文", onboarding_date="2025-07-10", source="主动联系", role="翻译",
                       gender="male", entity_type="individual",
                       status="Dormant", availability="空闲", domains="MMO",
                       cat_tools="Trados", currency="CNY", contract_status="即将到期",
                       contract_expiry="2026-07-10", nda_signed=True, responsiveness="一般",
                       cooperation_rating="正常合作", punctuality_rate=88, last_contact="2026-03-01"),
            Translator(name="陈静", wechat="chenjing", email="cj@example.com",
                       native_language="中文", onboarding_date="2026-01-20", source="推荐", role="审校",
                       gender="female", entity_type="individual",
                       translation_rate=130, review_rate=70, status="Probation",
                       current_project="诺诺", availability="健康", domains="休闲", cat_tools="Phrase",
                       currency="CNY", contract_status="有效", contract_expiry="2027-01-20",
                       responsiveness="一般", cooperation_rating="谨慎合作", punctuality_rate=80,
                       last_contact="2026-06-18"),
        ]
        s.add_all(ts)
        s.commit()
        i = {t.name: t.id for t in ts}
        s.add_all([
            TranslatorProjectExperience(
                translator_id=i["张明"], cooperation_source="our_company",
                project_status="current", project_name="燕云", role="翻译",
                source_lang="ZH", target_lang="EN",
            ),
            TranslatorProjectExperience(
                translator_id=i["张明"], cooperation_source="external",
                project_status="past", project_name="海外奇幻 RPG",
                external_company="海外发行商", role="审校",
                source_lang="EN", target_lang="ZH-HANS",
                start_date="2024-04-01", end_date="2024-11-30",
            ),
            TranslatorProjectExperience(
                translator_id=i["李娜"], cooperation_source="our_company",
                project_status="current", project_name="洛克王国", role="翻译",
                source_lang="ZH", target_lang="JA",
            ),
            TranslatorProjectExperience(
                translator_id=i["陈静"], cooperation_source="our_company",
                project_status="current", project_name="诺诺", role="审校",
            ),
        ])
        s.add_all([
            RateChange(translator_id=i["张明"], change_date="2026-05-10", task_type="翻译", original_rate=160,
                       new_rate=180, negotiator="Raven", reason="年度调价", result="成功", remarks="量稳定，上调"),
            RateChange(translator_id=i["李娜"], change_date="2026-06-01", task_type="翻译", original_rate=200,
                       new_rate=220, negotiator="Raven", reason="译员主动要求", result="成功", remarks="资深，原价低于市场"),
            RateChange(translator_id=i["李娜"], change_date="2026-06-10", task_type="LQE", original_rate=None,
                       new_rate=90, negotiator="Raven", reason="新增任务类型", result="成功", remarks="LQE 单价，与 LQA 不同"),
        ])
        s.add_all([
            PO(translator_id=i["张明"], settlement_month="2026-06", project="燕云", role="翻译", word_count=8000,
               rate=180, amount=1440, currency="CNY", status="已开票待付", po_number="PO-202606-001"),
            PO(translator_id=i["李娜"], settlement_month="2026-06", project="洛克王国", role="翻译", word_count=6500,
               rate=220, amount=1430, currency="CNY", status="已支付", po_number="PO-202606-002"),
            PO(translator_id=i["陈静"], settlement_month="2026-06", project="诺诺", role="翻译", word_count=5000,
               rate=130, amount=650, currency="CNY", status="未开票", po_number="PO-202606-003"),
            PO(translator_id=i["张明"], settlement_month="2026-06", project="海外SLG", role="翻译", word_count=3000,
               rate=30, amount=90, currency="USD", status="已开票待付", po_number="PO-202606-004"),
            # 故意让金额对不上（5000×80/1000=400，填 410）演示金额验算标红
            PO(translator_id=i["陈静"], settlement_month="2026-06", project="诺诺", role="审校", word_count=5000,
               rate=80, amount=410, currency="CNY", status="未开票", po_number="PO-202606-005"),
        ])
        s.add_all([
            Contract(translator_id=i["张明"], contract_number="C-2025-011", contract_type="框架协议",
                     sign_date="2025-01-01", expiry_date="2026-12-31", nda_signed=True, nda_expiry="2027-12-31",
                     status="有效"),
            Contract(translator_id=i["王伟"], contract_number="C-2025-027", contract_type="单项目合同",
                     sign_date="2025-07-10", expiry_date="2026-07-10", nda_signed=True, nda_expiry="2026-07-10",
                     status="即将到期"),
        ])
        s.add_all([
            LanguagePair(translator_id=i["张明"], source_lang="ZH", target_lang="EN",
                         translation_rate=180, mtpe_rate=120, review_rate=90, currency="CNY"),
            LanguagePair(translator_id=i["张明"], source_lang="ZH", target_lang="JA",
                         translation_rate=210, mtpe_rate=140, review_rate=100, currency="CNY"),
            LanguagePair(translator_id=i["李娜"], source_lang="ZH", target_lang="JA",
                         translation_rate=220, lqa_rate=80, lqe_rate=90, currency="CNY"),
        ])
        s.commit()
        s.add_all([
            QualityScore(translator_id=i["张明"], evaluation_period="2026-05", project="燕云", qa_type="LQE",
                         score=94, critical_errors=0, major_errors=1, minor_errors=3, reviewer="Raven",
                         feedback_notes="术语稳，个别润色"),
            QualityScore(translator_id=i["李娜"], evaluation_period="2026-06", project="洛克王国", qa_type="LQE",
                         score=97, critical_errors=0, major_errors=0, minor_errors=2, reviewer="Raven",
                         feedback_notes="高质量"),
        ])
        s.add(Complaint(translator_id=i["陈静"], date="2026-06-12", project="诺诺", complaint_type="质量不达标",
                        severity="一般", deduction_amount=200, resolution="已扣款", remarks="客户指出风格不一致"))
        s.add_all([
            Capacity(translator_id=i["张明"], period_year=2026, period_month=6, week_no=1, project="燕云", occupancy_pct=60),
            Capacity(translator_id=i["张明"], period_year=2026, period_month=6, week_no=2, project="燕云", occupancy_pct=60),
            Capacity(translator_id=i["李娜"], period_year=2026, period_month=6, week_no=1, project="洛克王国", occupancy_pct=100),
        ])
        s.add(PaymentInfo(translator_id=i["张明"], currency="CNY", bank_name="招商银行",
                          bank_account_enc=enc("6225888812345678"), id_card_enc=enc("310101199001011234"),
                          payee_name="张明", supports_wechat=True))
        s.add(PaymentAccount(
            translator_id=i["张明"], method="personal_bank", currency="CNY",
            account_name="张明", account_number_enc=enc("6225888812345678"),
            bank_name="招商银行", tax_id_enc=enc("310101199001011234"),
            is_default=False,
        ))
        s.add(ProjectPrice(
            translator_id=i["李娜"], project_name="洛克王国宣传批次",
            price_type="fixed", task_type="一口价", amount=1200,
            unit="project", currency="CNY", remarks="整批固定总价",
        ))
        s.commit()
        for tid in i.values():
            resync_translator(s, tid)
        s.commit()
