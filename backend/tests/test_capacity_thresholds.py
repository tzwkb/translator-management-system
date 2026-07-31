"""指定月份的项目字数分摊、默认产能与状态阈值回归测试。"""

from app.models import CapacityMonthOverride, Translator, TranslatorProjectExperience
from app.services import availability_snapshot, normalize_capacity_month


def snapshot(remaining_volume, daily_output=None):
    translator = Translator(
        name="产能测试",
        native_language="中文",
        onboarding_date="2026-07-30",
        gender="female",
        daily_output=daily_output,
    )
    project = TranslatorProjectExperience(
        cooperation_source="our_company",
        project_status="current",
        project_name="测试项目",
        role="翻译",
        remaining_volume=remaining_volume,
        start_date="2026-08-03",
        deadline="2026-08-31",
    )
    return availability_snapshot(
        translator,
        [project],
        month="2026-08",
        today="2026-07-31",
    )


def main():
    cases = [
        (19999, "空闲"),
        (20000, "健康"),
        (31999, "健康"),
        (32000, "饱和"),
        (40000, "饱和"),
        (40001, "警告"),
    ]
    failed = [
        (volume, expected, snapshot(volume)["computed_availability"])
        for volume, expected in cases
        if snapshot(volume)["computed_availability"] != expected
    ]
    default_snapshot = snapshot(40000)
    if default_snapshot["availability_basis"][0]["daily_capacity"] != 2000:
        failed.append(("默认日产能", 2000, default_snapshot))
    if default_snapshot["availability_basis"][0]["monthly_capacity"] != 40000:
        failed.append(("默认月产能", 40000, default_snapshot))
    if default_snapshot["allocated_words"] != 40000:
        failed.append(("全部在当月的字数", 40000, default_snapshot))

    translator = Translator(
        name="跨月测试",
        native_language="中文",
        onboarding_date="2026-07-30",
        gender="female",
        daily_output=2000,
    )
    cross_month = TranslatorProjectExperience(
        cooperation_source="our_company",
        project_status="current",
        project_name="跨月项目",
        role="翻译",
        remaining_volume=40000,
        start_date="2026-08-03",
        deadline="2026-09-25",
    )
    august = availability_snapshot(
        translator, [cross_month], month="2026-08", today="2026-07-31",
    )
    september = availability_snapshot(
        translator, [cross_month], month="2026-09", today="2026-07-31",
    )
    if august["availability_basis"][0]["month_work_days"] != 21:
        failed.append(("8 月工作日分摊", 21, august))
    if september["availability_basis"][0]["month_work_days"] != 19:
        failed.append(("9 月工作日分摊", 19, september))
    if august["allocated_words"] + september["allocated_words"] != 40000:
        failed.append(("跨月字数守恒", 40000, {"august": august, "september": september}))

    incomplete = TranslatorProjectExperience(
        cooperation_source="our_company",
        project_status="current",
        project_name="缺日期",
        role="翻译",
        remaining_volume=10000,
        deadline="2026-08-31",
    )
    incomplete_snapshot = availability_snapshot(
        translator, [incomplete], month="2026-08", today="2026-07-31",
    )
    if incomplete_snapshot["capacity_data_complete"] is not False:
        failed.append(("缺少日期应标记不完整", False, incomplete_snapshot))
    if incomplete_snapshot["computed_availability"] is not None:
        failed.append(("不完整数据不伪造状态", None, incomplete_snapshot))

    invalid_schedule = TranslatorProjectExperience(
        cooperation_source="our_company",
        project_status="current",
        project_name="旧数据异常日期",
        role="翻译",
        remaining_volume=10000,
        start_date="2026-99-01",
        deadline="2026-08-31",
    )
    invalid_snapshot = availability_snapshot(
        translator, [invalid_schedule], month="2026-08", today="2026-07-31",
    )
    if invalid_snapshot["capacity_data_complete"] is not False:
        failed.append(("旧数据非法日期应标记不完整", False, invalid_snapshot))
    try:
        normalize_capacity_month("0000-01", today="2026-07-31")
        failed.append(("非法年份应拒绝", "ValueError", "未抛错"))
    except ValueError:
        pass
    historical = availability_snapshot(
        translator, [cross_month], month="2026-06", today="2026-07-31",
    )
    if historical["computed_availability"] is not None:
        failed.append(("当前剩余量不得回算历史月", None, historical))
    zero_remaining = TranslatorProjectExperience(
        cooperation_source="our_company",
        project_status="current",
        project_name="已完成但未归档",
        remaining_volume=0,
        start_date="2026-07-25",
        deadline="2026-07-26",
    )
    zero_snapshot = availability_snapshot(
        translator, [zero_remaining], month="2026-08", today="2026-07-31",
    )
    if zero_snapshot["computed_load_pct"] != 0:
        failed.append(("剩余0字不应标记排期异常", 0, zero_snapshot))

    override = CapacityMonthOverride(
        translator_id=1,
        month="2026-08",
        status="警告",
        reason="译员本月不接新项目",
    )
    overridden = availability_snapshot(
        translator,
        [cross_month],
        month="2026-08",
        override=override,
        today="2026-07-31",
    )
    if overridden["effective_availability"] != "警告":
        failed.append(("按月人工修正", "警告", overridden))
    if overridden["availability_conflict"] is not True:
        failed.append(("人工修正冲突提示", True, overridden))
    if failed:
        print("失败:", failed)
        return 1
    print(
        f"capacity thresholds pass: {len(cases)}/{len(cases)}; "
        "cross-month allocation, incomplete-data guard and monthly override pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
