"""月度产能默认值与状态阈值回归测试。"""

from app.models import Translator, TranslatorProjectExperience
from app.services import availability_snapshot


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
    )
    return availability_snapshot(translator, [project])


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
    if failed:
        print("失败:", failed)
        return 1
    print(f"capacity thresholds pass: {len(cases)}/{len(cases)}; default 2000/day")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
