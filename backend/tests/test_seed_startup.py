"""验证部署默认空库、显式演示模式及重复启动。"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="translator-seed-") as directory:
        database = Path(directory) / "seed.db"
        env = os.environ.copy()
        env.update(DB_URL=f"sqlite:///{database}", AES_KEY="0" * 64)
        env.pop("SEED_DEMO_DATA", None)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                       env=env, check=True, capture_output=True)

        def start(seed=None):
            run_env = dict(env)
            if seed is not None:
                run_env["SEED_DEMO_DATA"] = seed
            subprocess.run([sys.executable, "-c", "from app.seed import seed; seed()"],
                           cwd=BACKEND, env=run_env, check=True, capture_output=True)
            with sqlite3.connect(database) as connection:
                return connection.execute("SELECT count(*) FROM translators").fetchone()[0]

        assert start() == 0
        assert start("0") == 0
        assert start("1") == 4
        assert start("1") == 4
        assert start("0") == 4
    print("5/5 seed startup checks passed")


if __name__ == "__main__":
    main()
