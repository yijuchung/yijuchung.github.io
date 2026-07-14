import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ReleaseScriptTests(unittest.TestCase):
    def test_uses_github_default_branch_when_remote_head_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            test_root = Path(temporary_directory)
            repository = test_root / "repository"
            scripts = repository / "scripts"
            commands = test_root / "bin"
            scripts.mkdir(parents=True)
            commands.mkdir()

            release_script = scripts / "release.sh"
            release_script.write_bytes(
                (REPOSITORY_ROOT / "scripts" / "release.sh").read_bytes()
            )
            release_script.chmod(release_script.stat().st_mode | stat.S_IXUSR)

            self.run_git(repository, "init", "--quiet", "--initial-branch=main")
            self.run_git(repository, "config", "user.name", "Release Test")
            self.run_git(repository, "config", "user.email", "release@example.com")
            self.run_git(
                repository,
                "remote",
                "add",
                "origin",
                "https://github.com/example/repository.git",
            )
            self.run_git(repository, "commit", "--allow-empty", "--quiet", "-m", "Initial")
            self.run_git(
                repository,
                "update-ref",
                "refs/remotes/origin/master",
                "HEAD",
            )
            self.run_git(
                repository,
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/master",
            )

            self.write_command(
                commands / "gh",
                """#!/bin/sh
case "$1 $2" in
  "auth status")
    exit 0
    ;;
  "repo view")
    printf 'main\\n'
    exit 0
    ;;
esac
exit 1
""",
            )
            self.write_command(commands / "docker", "#!/bin/sh\nexit 0\n")
            (repository / "dirty").touch()

            environment = os.environ.copy()
            environment["PATH"] = f"{commands}{os.pathsep}{environment['PATH']}"
            result = subprocess.run(
                [release_script, "v0.0.0"],
                cwd=repository,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "Commit or stash all working-tree changes before releasing.",
                result.stderr,
            )
            self.assertNotIn("default branch 'master'", result.stderr)

    def run_git(self, repository: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )

    def write_command(self, path: Path, contents: str) -> None:
        path.write_text(contents, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
