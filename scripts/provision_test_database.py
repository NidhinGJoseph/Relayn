"""Provision only test_relayn through the existing local Compose administrator."""

import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default=shutil.which("docker"))
    args = parser.parse_args()
    if not args.docker:
        parser.error("Docker is not on PATH; supply --docker with its executable path.")
    root = Path(__file__).resolve().parent.parent
    script = root / "infrastructure/postgres/provision-test-database.sh"
    # Normalize checkout line endings before feeding the Linux shell.
    result = subprocess.run(
        [args.docker, "compose", "exec", "-T", "postgres", "sh", "-s"],
        cwd=root,
        input=script.read_text().encode(),
        check=False,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
