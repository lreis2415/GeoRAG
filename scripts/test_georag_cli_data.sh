#!/usr/bin/env bash

# Run an end-to-end GeoRAG CLI smoke test with one checked-in fixture from
# tests/documents. The source file is never deleted or modified.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${GEORAG_PROFILE:-local}"
EMBEDDING_MODEL="${GEORAG_EMBEDDING_MODEL:-text-embedding-v4}"
CHAT_MODEL="${GEORAG_CHAT_MODEL:-qwen3.7-flash}"
QUESTION="${GEORAG_QUERY:-请概括这份文档的主题，并列出一个关键术语。}"
KB_ID="${GEORAG_KB_ID:-cli_data_test_$(date +%Y%m%d%H%M%S)}"
DATA_DIR="${GEORAG_DATA_DIR:-${ROOT_DIR}/tests/documents}"
SOURCE_FILE="${GEORAG_SOURCE_FILE:-}"
# A question may traverse embedding, retrieval, and chat-model services. Keep
# the normal CLI default at 60s, but give this end-to-end smoke test more time.
TIMEOUT="${GEORAG_TIMEOUT:-300}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/georag-cli-data-test.XXXXXX")"
KB_CREATED=0

# Only automatically clean knowledge bases created by this script. This guard
# prevents an accidental GEORAG_KB_ID from targeting an unrelated resource.
if [[ "${KB_ID}" != cli_data_test_* ]]; then
  echo "GEORAG_KB_ID must start with cli_data_test_" >&2
  exit 2
fi

if [[ -z "${SOURCE_FILE}" ]]; then
  SOURCE_FILE="$(find "${DATA_DIR}" -type f ! -name '.DS_Store' -print -quit)"
fi

if [[ -z "${SOURCE_FILE}" || ! -f "${SOURCE_FILE}" ]]; then
  echo "No source file found under ${DATA_DIR}." >&2
  echo "Set GEORAG_SOURCE_FILE=/path/to/a/file to choose one explicitly." >&2
  exit 2
fi

if command -v georag >/dev/null 2>&1; then
  CLI=(georag)
else
  CLI=(python -m georag_cli)
fi
CLI+=(--profile "${PROFILE}" --non-interactive --output json --timeout "${TIMEOUT}")

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "${KB_CREATED}" == 1 ]]; then
    echo "[cleanup] deleting ${KB_ID}" >&2
    if ! "${CLI[@]}" kb delete "${KB_ID}" --yes; then
      echo "[cleanup] warning: failed to delete ${KB_ID}" >&2
    fi
  fi
  rm -rf "${TMP_DIR}"
  exit "${status}"
}
trap cleanup EXIT

run() {
  echo "+ ${CLI[*]} $*" >&2
  "${CLI[@]}" "$@"
}

echo "Using source: ${SOURCE_FILE}"
echo "Using profile: ${PROFILE}"
echo "Using temporary knowledge base: ${KB_ID}"

# The human must have completed `georag auth login` before this script runs.
run auth status
run models list
run kb create "${KB_ID}" --embedding-model "${EMBEDDING_MODEL}"
KB_CREATED=1
run kb add "${KB_ID}" "${SOURCE_FILE}"
run kb show "${KB_ID}"
run kb files "${KB_ID}"
run kb ask "${KB_ID}" --chat-model "${CHAT_MODEL}" --query "${QUESTION}"

# The uploaded filename is the local basename. Download into a temporary
# directory and compare bytes without touching the original data file.
DOWNLOADED="${TMP_DIR}/$(basename "${SOURCE_FILE}")"
run file list
run file download "$(basename "${SOURCE_FILE}")" --destination "${DOWNLOADED}"
cmp -s "${SOURCE_FILE}" "${DOWNLOADED}"
echo "Downloaded file matches the source byte-for-byte."

run kb delete "${KB_ID}" --yes
KB_CREATED=0
run kb list
echo "GeoRAG CLI data smoke test passed."
