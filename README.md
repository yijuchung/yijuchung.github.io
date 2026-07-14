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

The contribution sync is intentionally local-only. It requires Python 3, GitHub CLI, and an authenticated GitHub account matching `yijuchung`.

```sh
gh auth refresh -h github.com -s repo,read:org,read:user
python3 scripts/sync_contributions.py
```

The script writes `_data/metrics.json`. Commit that generated file when the public site should be refreshed.

Private activity is reduced to aggregate counts. The GraphQL request does not query private repository names, organizations, branches, or content. The script refuses to run in CI and refuses to publish private metrics when the authenticated user does not match the profile owner.

The sync intentionally ignores `GH_TOKEN` and `GITHUB_TOKEN` environment overrides. It uses the local `gh` keyring credential so an ephemeral token cannot silently change which contributions GitHub classifies as private.

## Deploy

GitHub Pages builds and deploys the Jekyll site through `.github/workflows/pages.yml` whenever `master` changes. In the repository settings, set **Pages > Build and deployment > Source** to **GitHub Actions**.

The workflow never accesses private repositories or credentials. Private contribution data reaches the public site only through the locally generated aggregate JSON file.
