#!/usr/bin/env bash

set -euo pipefail

case "${CI:-}${GITHUB_ACTIONS:-}" in
  *1*|*[Tt][Rr][Uu][Ee]*|*[Yy][Ee][Ss]*)
    echo "Isocalendar sync is intentionally local-only and cannot run in CI." >&2
    exit 2
    ;;
esac

if [[ -z "${METRICS_TOKEN:-}" ]]; then
  echo "Set METRICS_TOKEN to a GitHub token that can read the intended contributions." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to generate the lowlighter isocalendar." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but its daemon is not running." >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_path="$repo_root/assets/metrics/isocalendar.svg"
metrics_image="ghcr.io/lowlighter/metrics:v3.34"
metrics_platform="linux/amd64"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"; unset INPUT_TOKEN' EXIT

export INPUT_TOKEN="$METRICS_TOKEN"
export INPUT_USER="yijuchung"
export INPUT_FILENAME="isocalendar.svg"
export INPUT_BASE=""
export INPUT_PLUGIN_ISOCALENDAR="yes"
export INPUT_PLUGIN_ISOCALENDAR_DURATION="half-year"
export INPUT_CONFIG_DISPLAY="large"
export INPUT_CONFIG_OUTPUT="svg"
export INPUT_CONFIG_ANIMATIONS="no"
export INPUT_CONFIG_TIMEZONE="America/Los_Angeles"
export INPUT_OUTPUT_ACTION="none"
export INPUT_EXTRAS_CSS='
svg {
  color: #b0b0b0 !important;
  font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif !important;
}
h2, h3 {
  color: #dedede !important;
}
.field svg {
  fill: #919191 !important;
}
'

docker run --platform "$metrics_platform" --init --rm \
  --env INPUT_TOKEN \
  --env INPUT_USER \
  --env INPUT_FILENAME \
  --env INPUT_BASE \
  --env INPUT_PLUGIN_ISOCALENDAR \
  --env INPUT_PLUGIN_ISOCALENDAR_DURATION \
  --env INPUT_CONFIG_DISPLAY \
  --env INPUT_CONFIG_OUTPUT \
  --env INPUT_CONFIG_ANIMATIONS \
  --env INPUT_CONFIG_TIMEZONE \
  --env INPUT_OUTPUT_ACTION \
  --env INPUT_EXTRAS_CSS \
  --volume "$temporary_dir:/renders" \
  "$metrics_image"

unset INPUT_TOKEN

generated_path="$temporary_dir/isocalendar.svg"
if [[ ! -s "$generated_path" ]] || ! grep -q '<svg' "$generated_path"; then
  echo "lowlighter/metrics did not produce a valid SVG." >&2
  exit 1
fi

mkdir -p "$(dirname "$output_path")"
python3 - "$generated_path" "$output_path" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
svg = source.read_text(encoding="utf-8")

palette = {
    "#ebedf0": "#343231",
    "#9be9a8": "#5f5f5f",
    "#40c463": "#919191",
    "#30a14e": "#b0b0b0",
    "#216e39": "#dedede",
    "#0366d6": "#dedede",
    "#959da5": "#919191",
    "#777": "#b0b0b0",
    "#7f00ff": "#5f5f5f",
    "#a933ff": "#919191",
    "#007fff": "#b0b0b0",
    "#00ff7f": "#dedede",
    "#ff0": "#b0b0b0",
    "#ff7f00": "#dedede",
    "#ffee4a": "#5f5f5f",
    "#ffc501": "#919191",
    "#fe9600": "#b0b0b0",
    "#03001c": "#dedede",
    "#0a3069": "#5f5f5f",
    "#0969da": "#919191",
    "#54aeff": "#b0b0b0",
    "#b6e3ff": "#dedede",
}
for original, replacement in palette.items():
    svg = svg.replace(original, replacement)
svg = svg.replace("color:red;fill:red", "color:#dedede;fill:#dedede")

attribution = (
    "<!-- Generated locally with lowlighter/metrics v3.34, "
    "isocalendar half-year plugin. -->\n"
)
destination.write_text(attribution + svg, encoding="utf-8")
PY

echo "Wrote $output_path"
