"""Run Alembic migrations: alembic upgrade head."""

import subprocess
import sys


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
