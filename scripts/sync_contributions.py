#!/usr/bin/env python3
"""Publish aggregate GitHub contribution metrics without private repository metadata."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_USERNAME = "yijuchung"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "_data" / "metrics.json"
CONTRIBUTION_LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

QUERY = """
query ContributionMetrics($login: String!, $from: DateTime!, $to: DateTime!) {
  viewer {
    login
  }
  user(login: $login) {
    login
    name
    url
    createdAt
    followers(first: 1) {
      totalCount
    }
    repositories(first: 1, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
    }
    contributionsCollection(from: $from, to: $to) {
      hasAnyRestrictedContributions
      restrictedContributionsCount
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            contributionLevel
            date
          }
        }
      }
    }
  }
  rateLimit {
    remaining
    resetAt
  }
}
"""


class SyncError(RuntimeError):
    """Raised when contribution metrics cannot be safely synchronized."""


def iso_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def github_cli_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("GH_TOKEN", None)
    environment.pop("GITHUB_TOKEN", None)
    return environment


def run_graphql(username: str, start: datetime, end: datetime) -> dict[str, Any]:
    command = [
        "gh",
        "api",
        "--hostname",
        "github.com",
        "graphql",
        "-f",
        f"query={QUERY}",
        "-F",
        f"login={username}",
        "-F",
        f"from={iso_datetime(start)}",
        "-F",
        f"to={iso_datetime(end)}",
    ]

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=github_cli_environment(),
        )
    except FileNotFoundError as exc:
        raise SyncError("GitHub CLI is required. Install and authenticate gh before syncing.") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or "GitHub GraphQL request failed."
        raise SyncError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SyncError("GitHub returned an invalid JSON response.") from exc

    if payload.get("errors"):
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in payload["errors"])
        raise SyncError(messages)

    return payload


def calculate_streaks(days: list[dict[str, Any]], today: date) -> tuple[int, int]:
    counts = {
        date.fromisoformat(day["date"]): int(day["count"])
        for day in days
    }

    longest = 0
    running = 0
    for day in sorted(counts):
        if counts[day] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    cursor = today
    if counts.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)

    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    return current, longest


def build_metrics(payload: dict[str, Any], generated_at: datetime) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SyncError("GitHub response did not contain contribution data.")

    viewer = data.get("viewer")
    user = data.get("user")
    if not isinstance(viewer, dict) or not isinstance(user, dict):
        raise SyncError("GitHub account data was unavailable.")
    if viewer.get("login", "").casefold() != user.get("login", "").casefold():
        raise SyncError(
            "Authenticated GitHub user must match the profile owner so private contributions are included."
        )

    collection = user.get("contributionsCollection")
    if not isinstance(collection, dict):
        raise SyncError("GitHub contribution collection was unavailable.")

    contribution_calendar = collection.get("contributionCalendar")
    if not isinstance(contribution_calendar, dict):
        raise SyncError("GitHub contribution calendar was unavailable.")

    days: list[dict[str, Any]] = []
    for week_index, week in enumerate(contribution_calendar.get("weeks", [])):
        for contribution_day in week.get("contributionDays", []):
            day_date = date.fromisoformat(contribution_day["date"])
            level_name = contribution_day["contributionLevel"]
            if level_name not in CONTRIBUTION_LEVELS:
                raise SyncError(f"Unknown contribution level: {level_name}")

            days.append(
                {
                    "date": contribution_day["date"],
                    "count": int(contribution_day["contributionCount"]),
                    "level": CONTRIBUTION_LEVELS[level_name],
                    "week": week_index,
                    "weekday": (day_date.weekday() + 1) % 7,
                }
            )

    if not days:
        raise SyncError("GitHub returned an empty contribution calendar.")

    days.sort(key=lambda day: day["date"])
    total = int(contribution_calendar["totalContributions"])
    private = int(collection["restrictedContributionsCount"])
    if private > total:
        raise SyncError("Private contribution count exceeded the total contribution count.")

    current_streak, longest_streak = calculate_streaks(days, generated_at.date())
    peak_day = max(days, key=lambda day: int(day["count"]))

    return {
        "generated_at": iso_datetime(generated_at),
        "profile": {
            "login": user["login"],
            "name": user.get("name") or user["login"],
            "github_url": user["url"],
            "followers": int(user["followers"]["totalCount"]),
            "public_repositories": int(user["repositories"]["totalCount"]),
            "account_created_at": user["createdAt"],
        },
        "period": {
            "from": days[0]["date"],
            "to": days[-1]["date"],
            "days": len(days),
        },
        "totals": {
            "contributions": total,
            "public_contributions": total - private,
            "private_contributions": private,
            "commits": int(collection["totalCommitContributions"]),
            "issues": int(collection["totalIssueContributions"]),
            "pull_requests": int(collection["totalPullRequestContributions"]),
            "pull_request_reviews": int(collection["totalPullRequestReviewContributions"]),
            "repositories_created": int(collection["totalRepositoryContributions"]),
        },
        "activity": {
            "active_days": sum(1 for day in days if int(day["count"]) > 0),
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "peak_day": {
                "date": peak_day["date"],
                "contributions": int(peak_day["count"]),
            },
        },
        "calendar": days,
    }


def write_metrics(metrics: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            delete=False,
        ) as temporary_file:
            json.dump(metrics, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync aggregate public and private GitHub contribution metrics."
    )
    parser.add_argument("--user", default=DEFAULT_USERNAME, help="GitHub login to synchronize.")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of calendar days to include, from 1 through 365.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination JSON file.",
    )
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")
    return args


def main() -> int:
    in_ci = any(
        os.environ.get(variable, "").casefold() in {"1", "true", "yes"}
        for variable in ("CI", "GITHUB_ACTIONS")
    )
    if in_ci:
        print("Contribution sync is intentionally local-only and cannot run in CI.", file=sys.stderr)
        return 2

    args = parse_args()
    generated_at = datetime.now(timezone.utc)
    start = generated_at - timedelta(days=args.days - 1)

    try:
        payload = run_graphql(args.user, start, generated_at)
        metrics = build_metrics(payload, generated_at)
    except SyncError as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        return 1

    write_metrics(metrics, args.output.resolve())
    print(
        f"Wrote {metrics['totals']['contributions']} aggregate contributions "
        f"to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
