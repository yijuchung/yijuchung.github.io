import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SyncIsocalendarScriptTests(unittest.TestCase):
    def test_requests_the_metrics_image_platform_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            test_root = Path(temporary_directory)
            repository = test_root / "repository"
            scripts = repository / "scripts"
            commands = test_root / "bin"
            scripts.mkdir(parents=True)
            commands.mkdir()

            sync_script = scripts / "sync_isocalendar.sh"
            sync_script.write_bytes(
                (REPOSITORY_ROOT / "scripts" / "sync_isocalendar.sh").read_bytes()
            )
            sync_script.chmod(sync_script.stat().st_mode | stat.S_IXUSR)

            docker_log = test_root / "docker-arguments"
            self.write_command(
                commands / "docker",
                """#!/bin/sh
set -eu

if [ "$1" = "info" ]; then
  exit 0
fi

[ "$1" = "run" ]
printf '%s\\n' "$@" > "$DOCKER_LOG"

render_directory=
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--volume" ]; then
    shift
    render_directory="${1%%:*}"
  fi
  shift
done

[ -n "$render_directory" ]
printf '<svg></svg>\\n' > "$render_directory/isocalendar.svg"
""",
            )

            environment = os.environ.copy()
            environment.pop("CI", None)
            environment.pop("GITHUB_ACTIONS", None)
            environment["DOCKER_LOG"] = str(docker_log)
            environment["METRICS_TOKEN"] = "test-token"
            environment["PATH"] = f"{commands}{os.pathsep}{environment['PATH']}"
            result = subprocess.run(
                [sync_script],
                cwd=repository,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = docker_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(arguments[:3], ["run", "--platform", "linux/amd64"])
            self.assertEqual(arguments[-1], "ghcr.io/lowlighter/metrics:v3.34")

    def write_command(self, path: Path, contents: str) -> None:
        path.write_text(contents, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
