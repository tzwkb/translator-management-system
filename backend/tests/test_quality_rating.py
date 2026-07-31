"""累计 LQE 分数自动评级边界测试。"""

from app.services import quality_rating


def main():
    cases = [
        (None, None),
        (100, "S"),
        (95, "S"),
        (94.99, "A"),
        (90, "A"),
        (89.99, "A-"),
        (85, "A-"),
        (84.99, "B"),
        (80, "B"),
        (79.99, "C"),
        (60, "C"),
        (59.99, "D"),
        (0, "D"),
    ]
    failed = [
        (score, expected, quality_rating(score))
        for score, expected in cases
        if quality_rating(score) != expected
    ]
    if failed:
        print("失败:", failed)
        return 1
    print(f"quality rating boundaries pass: {len(cases)}/{len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
