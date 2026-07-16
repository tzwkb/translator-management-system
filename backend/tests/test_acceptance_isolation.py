"""验收测试默认隔离运行，不应默认写开发端口。"""

import importlib.util
import os
from pathlib import Path


def main():
    os.environ.pop("BASE", None)
    spec = importlib.util.spec_from_file_location(
        "acceptance_module",
        Path(__file__).with_name("test_acceptance.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.BASE is not None:
        print("失败: 未设置 BASE 时不应默认打开发服务", mod.BASE)
        return 1
    if not callable(getattr(mod, "start_isolated_server", None)):
        print("失败: 缺少隔离验收服务启动器")
        return 1
    print("acceptance defaults to isolated server")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
