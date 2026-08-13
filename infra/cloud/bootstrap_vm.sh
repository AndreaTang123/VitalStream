#!/usr/bin/env bash
# One-shot bootstrap for a fresh Ubuntu cloud VM (Azure/AWS, per PRD 4.3):
# installs Docker, clones the repo, curls the datasets down locally on the
# VM, and brings up the docker-compose stack.
#
# Run this ON the VM (e.g. over SSH), not on your laptop:
#   curl -fsSL https://raw.githubusercontent.com/AndreaTang123/VitalStream/main/infra/cloud/bootstrap_vm.sh | bash
# or, if you've already cloned the repo there:
#   ./infra/cloud/bootstrap_vm.sh
#
# Env vars (all optional):
#   REPO_URL   git remote to clone           (default: this repo's origin)
#   REPO_DIR   where to clone/find the repo  (default: ~/vitalstream)
#   DATASETS   which datasets to fetch       (default: both — see download_datasets.sh)

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/AndreaTang123/VitalStream.git}"
REPO_DIR="${REPO_DIR:-$HOME/vitalstream}"
DATASETS="${DATASETS:-}"

if ! command -v docker >/dev/null; then
  echo "== installing Docker Engine + compose plugin =="
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl unzip
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "Docker installed — you may need to log out/in for group membership to take effect."
fi

if [ -d "$REPO_DIR/.git" ]; then
  echo "== $REPO_DIR already exists, pulling latest =="
  git -C "$REPO_DIR" pull --ff-only
else
  echo "== cloning $REPO_URL into $REPO_DIR =="
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "== copied .env.example -> .env, fill in real secrets (OPENAI_API_KEY etc.) before relying on Layer 2 =="
fi

echo "== fetching datasets =="
# shellcheck disable=SC2086
./data/scripts/download_datasets.sh $DATASETS

echo "== starting docker compose stack =="
docker compose up -d

docker compose ps
