#!/usr/bin/env bash
# Downloads WESAD and/or PPG-DaLiA into data/raw/ (PRD 2.2/9).
#
# Meant to run on the machine that actually runs `docker compose up` — i.e.
# the cloud VM, not the dev laptop — since the ingestion service will read
# replay data from wherever this lands. Needs only curl + unzip.
#
# Both datasets are hosted on UCI's ML Repository as plain zip files with no
# login/DUA wall, so a direct curl works:
#   WESAD:     https://archive.ics.uci.edu/dataset/465
#   PPG-DaLiA: https://archive.ics.uci.edu/dataset/495
#
# Usage:
#   ./download_datasets.sh                # both datasets
#   ./download_datasets.sh wesad          # just WESAD
#   ./download_datasets.sh ppg_dalia      # just PPG-DaLiA
#   ./download_datasets.sh --force        # re-download even if already present
#   DATA_DIR=/mnt/data ./download_datasets.sh   # download elsewhere

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${DATA_DIR:-$SCRIPT_DIR/../raw}"
FORCE=0
DATASETS=()

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    wesad|ppg_dalia) DATASETS+=("$arg") ;;
    *) echo "unknown argument: $arg (expected: wesad, ppg_dalia, --force)" >&2; exit 1 ;;
  esac
done
[ ${#DATASETS[@]} -eq 0 ] && DATASETS=(wesad ppg_dalia)

# Plain function instead of `declare -A` (bash 4+ only) — macOS ships bash 3.2
# as /bin/bash with no associative arrays, and this needs to run there too.
url_for() {
  case "$1" in
    wesad) echo "https://archive.ics.uci.edu/static/public/465/wesad+wearable+stress+and+affect+detection.zip" ;;
    ppg_dalia) echo "https://archive.ics.uci.edu/static/public/495/ppg+dalia.zip" ;;
  esac
}

for tool in curl unzip; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool (apt-get install -y curl unzip)" >&2; exit 1; }
done

mkdir -p "$DATA_DIR"

for name in "${DATASETS[@]}"; do
  target="$DATA_DIR/$name"
  if [ "$FORCE" -ne 1 ] && [ -d "$target" ] && [ "$(ls -A "$target" 2>/dev/null)" ]; then
    echo "== $name already present at $target, skipping (use --force to re-download) =="
    continue
  fi

  url="$(url_for "$name")"
  zip_path="$DATA_DIR/$name.zip"
  echo "== downloading $name from $url =="
  curl -fL --progress-bar -o "$zip_path" "$url"

  echo "== extracting $name into $target =="
  rm -rf "$target"
  mkdir -p "$target"
  unzip -q "$zip_path" -d "$target"
  rm -f "$zip_path"

  # UCI packages some datasets as a zip-of-a-zip (observed for ppg_dalia: the
  # outer zip contains a single inner `data.zip` alongside a readme) — unwrap
  # one more level so $target ends up with the actual dataset files, not an
  # unopened zip sitting next to a PDF.
  for inner_zip in "$target"/*.zip; do
    [ -e "$inner_zip" ] || continue
    echo "== unwrapping nested $(basename "$inner_zip") =="
    unzip -q "$inner_zip" -d "$target"
    rm -f "$inner_zip"
  done

  echo "== $name ready at $target =="
done

echo "Done. DATA_DIR=$DATA_DIR"
