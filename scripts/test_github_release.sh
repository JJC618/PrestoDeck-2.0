#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/JJC618/PrestoDeck-2.0.git}"
BRANCH="${BRANCH:-main}"
PRIVATE_SECRETS="${PRIVATE_SECRETS:-}"
KEEP_CLONE="${KEEP_CLONE:-1}"

WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/prestodeck-release-test.XXXXXX")"
CLONE_DIR="${WORK_ROOT}/PrestoDeck-2.0"

echo "Cloning ${REPO_URL} (${BRANCH})..."
git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${CLONE_DIR}" >/dev/null

cd "${CLONE_DIR}"

required_files="
README.md
CHANGELOG.md
src/main.py
src/base.py
src/secrets.example.py
src/applications/spotify/spotify.py
src/applications/spotify/spotify_assets.py
src/applications/spotify/spotify_bridge_client.py
src/applications/spotify/spotify_controls.py
src/applications/spotify/spotify_settings.py
src/applications/spotify/spotify_state.py
src/applications/spotify/spotify_usage.py
src/applications/spotify/spotify_url.py
pi_bridge/spotify_bridge.py
pi_bridge/install_service.sh
pi_bridge/presto-spotify-bridge.service
sd_card/README.md
sd_card/icon.png
"

for file in ${required_files}; do
  if [[ ! -e "${file}" ]]; then
    echo "Missing required file: ${file}" >&2
    exit 1
  fi
done

if [[ -e src/secrets.py ]]; then
  echo "Public repo should not include src/secrets.py" >&2
  exit 1
fi

icon_count="$(find sd_card/icons -type f -name '*.png' | wc -l | tr -d ' ')"
if [[ "${icon_count}" -lt 15 ]]; then
  echo "Expected SD card icons, found only ${icon_count}" >&2
  exit 1
fi

if grep -R -E "refresh_token['\"]?[[:space:]]*:[[:space:]]*['\"][A-Za-z0-9_-]{20,}|client_secret['\"]?[[:space:]]*:[[:space:]]*['\"][0-9a-f]{32}" \
  --exclude-dir=.git . >/dev/null; then
  echo "Possible private Spotify credentials found in public files" >&2
  exit 1
fi

echo "Checking Python syntax..."
python3 -m py_compile \
  adhoc/generate_token.py \
  pi_bridge/spotify_bridge.py \
  src/applications/spotify/spotify.py \
  src/applications/spotify/spotify_assets.py \
  src/applications/spotify/spotify_bridge_client.py \
  src/applications/spotify/spotify_controls.py \
  src/applications/spotify/spotify_settings.py \
  src/applications/spotify/spotify_state.py \
  src/applications/spotify/spotify_usage.py \
  src/applications/spotify/spotify_url.py \
  src/base.py \
  src/main.py

if [[ -n "${PRIVATE_SECRETS}" ]]; then
  if [[ ! -f "${PRIVATE_SECRETS}" ]]; then
    echo "PRIVATE_SECRETS was set but file was not found: ${PRIVATE_SECRETS}" >&2
    exit 1
  fi
  cp "${PRIVATE_SECRETS}" src/secrets.py
  echo "Copied private secrets into fresh clone: ${CLONE_DIR}/src/secrets.py"
fi

echo
echo "GitHub release test passed."
echo "Fresh clone is here:"
echo "${CLONE_DIR}"
echo
echo "To test on your own Presto, upload from that fresh clone:"
echo "- ${CLONE_DIR}/src/main.py"
echo "- ${CLONE_DIR}/src/base.py"
echo "- ${CLONE_DIR}/src/applications"
if [[ -n "${PRIVATE_SECRETS}" ]]; then
  echo "- ${CLONE_DIR}/src/secrets.py"
else
  echo
  echo "This clean clone does not contain private secrets yet."
  echo "To make a device-ready clone, run:"
  echo "PRIVATE_SECRETS=/Users/joeclarke/PrestoDeck/src/secrets.py scripts/test_github_release.sh"
fi
echo
echo "Copy SD files from:"
echo "- ${CLONE_DIR}/sd_card"

if [[ "${KEEP_CLONE}" != "1" ]]; then
  rm -rf "${WORK_ROOT}"
fi
