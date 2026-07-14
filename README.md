# yijuchung.github.io

A Markdown-first Jekyll site for Yi-Ju Chung's engineering profile and aggregate GitHub activity.

## Local preview

Use Ruby 3.3, matching `.ruby-version`. On macOS with Homebrew:

```sh
brew install ruby@3.3
export PATH="$(brew --prefix ruby@3.3)/bin:$PATH"
bundle install
bundle exec jekyll serve
```

Open <http://127.0.0.1:4000>.

## Sync contribution metrics

Private contribution sync is intentionally local-only. It requires Python 3, GitHub CLI, and an authenticated GitHub account matching `yijuchung`.

```sh
gh auth refresh -h github.com -s repo,read:org,read:user
python3 scripts/sync_contributions.py
```

The script writes `_data/metrics.json`. The site labels its timestamp as the private snapshot time and links separately to live public activity on GitHub.

Private activity is reduced to aggregate counts. The GraphQL request does not query private repository names, organizations, branches, or content. The script refuses to run in CI and refuses to publish private metrics when the authenticated user does not match the profile owner.

The sync intentionally ignores `GH_TOKEN` and `GITHUB_TOKEN` environment overrides. It uses the local `gh` keyring credential so an ephemeral token cannot silently change which contributions GitHub classifies as private.

### Generate the half-year isocalendar

The contribution cadence uses the official [`lowlighter/metrics` isocalendar plugin](https://github.com/lowlighter/metrics/tree/master/source/plugins/isocalendar) with its `half-year` duration. Generate the SVG locally with Docker:

```sh
export METRICS_TOKEN="$(env -u GH_TOKEN gh auth token)"
scripts/sync_isocalendar.sh
unset METRICS_TOKEN
```

The wrapper pins `ghcr.io/lowlighter/metrics:v3.34`, explicitly requests the image's published `linux/amd64` platform, disables animations, applies the site's graphite palette, and writes `assets/metrics/isocalendar.svg`. ARM hosts require Docker's AMD64 emulation support. The wrapper refuses to run in CI and never prints or persists the token.

Commit `_data/metrics.json` and `assets/metrics/isocalendar.svg` together when private metrics should be refreshed.

## Release

Create a release from a clean checkout of `main`:

```sh
scripts/release.sh v1.0.0
```

The script refreshes both private-contribution artifacts, commits them, creates an annotated tag, atomically pushes `main` and the tag, and creates a GitHub release with generated notes. It requires GitHub CLI authentication with access to private contributions and a running Docker daemon.

## Deploy

GitHub Pages builds and deploys the Jekyll site through `.github/workflows/pages.yml` whenever `main` changes. In the repository settings, set **Pages > Build and deployment > Source** to **GitHub Actions**.

The workflow never accesses private repositories or credentials. Private contribution data reaches the public site only through the locally generated aggregate JSON file.
