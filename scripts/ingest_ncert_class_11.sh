#!/usr/bin/env bash
# Ingest NCERT Class 11 — India: Physical Environment into the existing
# rajasthan_geography subject tree. The merge stage (cosine prefilter +
# stdlib HashBagEmbedder) runs automatically because the subject tree
# already exists on disk.
#
# Source: https://ncert.nic.in/textbook.php?kegy1=0-6
#         (kegy1dd.zip = full book, prelim + 6 chapters, ~10.2 MB)
#
# Prerequisite: OPENROUTER_API_KEY must be set in backend/.env (or exported)
# Cost: ~$1–3 in OpenRouter credits, runs ~8–10 minutes end-to-end.
#
# Usage:
#   ./scripts/ingest_ncert_class_11.sh
#
# After completion the merged tree shows up at:
#   database/skills/rajasthan_geography/
#     - existing leaves now have ## Source 2 NCERT sections appended where
#       cosine ≥ 0.92 matched
#     - non-matched NCERT leaves added under best-fit chapter (slug-overlap)
#       or under a fresh chapter when nothing matches
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}/backend"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  if [[ -f .env ]] && grep -q '^OPENROUTER_API_KEY=' .env; then
    echo "Reading OPENROUTER_API_KEY from backend/.env"
  else
    echo "ERROR: OPENROUTER_API_KEY not set. Either export it or add it to backend/.env" >&2
    exit 1
  fi
fi

echo "=== Gemma Tutor — NCERT Class 11 ingest ==="
echo "Subject:      rajasthan_geography (existing — will merge)"
echo "Source:       https://ncert.nic.in/textbook/pdf/kegy1dd.zip"
echo "Authority:    0  (NCERT — outranks all coaching sources)"
echo "Model:        google/gemma-4-26b-a4b-it"
echo

MODEL_INGESTION=google/gemma-4-26b-a4b-it \
uv run python "${REPO_ROOT}/scripts/ingest_v2.py" \
  --source "https://ncert.nic.in/textbook/pdf/kegy1dd.zip" \
  --subject-slug rajasthan_geography \
  --book-slug ncert_class_11_india_physical \
  --book-name "NCERT Class 11 — India: Physical Environment" \
  --publisher NCERT \
  --authority-rank 0 \
  --scope rajasthan
