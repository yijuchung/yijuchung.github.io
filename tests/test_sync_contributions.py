import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.sync_contributions import (
    SyncError,
    build_metrics,
    calculate_streaks,
    github_cli_environment,
)


def sample_payload(viewer: str = "yijuchung") -> dict:
    return {
        "data": {
            "viewer": {"login": viewer},
            "user": {
                "login": "yijuchung",
                "name": "Yi-Ju Chung",
                "url": "https://github.com/yijuchung",
                "createdAt": "2010-08-16T09:14:15Z",
                "followers": {"totalCount": 6},
                "repositories": {"totalCount": 2},
                "contributionsCollection": {
                    "hasAnyRestrictedContributions": True,
                    "restrictedContributionsCount": 3,
                    "totalCommitContributions": 6,
                    "totalIssueContributions": 1,
                    "totalPullRequestContributions": 2,
                    "totalPullRequestReviewContributions": 4,
                    "totalRepositoryContributions": 0,
                    "contributionCalendar": {
                        "totalContributions": 10,
                        "weeks": [
                            {
                                "contributionDays": [
                                    {
                                        "contributionCount": 1,
                                        "contributionLevel": "FIRST_QUARTILE",
                                        "date": "2026-07-11",
                                    },
                                    {
                                        "contributionCount": 2,
                                        "contributionLevel": "SECOND_QUARTILE",
                                        "date": "2026-07-12",
                                    },
                                    {
                                        "contributionCount": 7,
                                        "contributionLevel": "FOURTH_QUARTILE",
                                        "date": "2026-07-13",
                                    },
                                    {
                                        "contributionCount": 0,
                                        "contributionLevel": "NONE",
                                        "date": "2026-07-14",
                                    },
                                ]
                            }
                        ],
                    },
                },
            },
            "rateLimit": {"remaining": 4999, "resetAt": "2026-07-14T21:00:00Z"},
        }
    }


class ContributionMetricsTests(unittest.TestCase):
    def test_ignores_environment_token_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {"GH_TOKEN": "ephemeral", "GITHUB_TOKEN": "actions", "SAFE_VALUE": "preserved"},
            clear=True,
        ):
            environment = github_cli_environment()

        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertEqual(environment["SAFE_VALUE"], "preserved")

    def test_builds_public_safe_aggregate_metrics(self) -> None:
        generated_at = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)

        metrics = build_metrics(sample_payload(), generated_at)

        self.assertEqual(metrics["totals"]["contributions"], 10)
        self.assertEqual(metrics["totals"]["public_contributions"], 7)
        self.assertEqual(metrics["totals"]["private_contributions"], 3)
        self.assertEqual(metrics["activity"]["active_days"], 3)
        self.assertEqual(metrics["activity"]["current_streak"], 3)
        self.assertEqual(metrics["activity"]["longest_streak"], 3)
        self.assertNotIn("rateLimit", metrics)
        self.assertNotIn("private repository", json.dumps(metrics).lower())

    def test_requires_authentication_as_profile_owner(self) -> None:
        with self.assertRaisesRegex(SyncError, "must match the profile owner"):
            build_metrics(
                sample_payload(viewer="another-user"),
                datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),
            )

    def test_streak_ends_yesterday_when_today_is_inactive(self) -> None:
        current, longest = calculate_streaks(
            [
                {"date": "2026-07-11", "count": 1},
                {"date": "2026-07-12", "count": 1},
                {"date": "2026-07-13", "count": 1},
                {"date": "2026-07-14", "count": 0},
            ],
            datetime(2026, 7, 14, tzinfo=timezone.utc).date(),
        )

        self.assertEqual(current, 3)
        self.assertEqual(longest, 3)


if __name__ == "__main__":
    unittest.main()
