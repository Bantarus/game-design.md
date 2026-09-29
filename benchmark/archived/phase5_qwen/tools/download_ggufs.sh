#!/usr/bin/env bash
# Download the GGUF files for the v0.2 Phase 5 instrument bundles.
#
# This is a harness-build action — the *files themselves* (and their
# SHA-256 hashes) are what the InstrumentBundle / JudgeBundle pin. The
# script is committed so the download is reproducible and so future
# trial-zero readers can audit exactly which files were used.
#
# Default destination: ~/llama.cpp/models/ (alongside existing
# ggml-vocab-*.gguf tokenizer fixtures). Override with $MODELS_DIR.
#
# Requirements:
#   - huggingface_hub[cli] installed; `hf` on PATH
#   - HF token authenticated (`hf auth whoami` returns a user)
#   - ~36 GB free disk space at the destination
#
# Usage:
#   benchmark/tools/download_ggufs.sh
#
# Or to a custom destination:
#   MODELS_DIR=/custom/path benchmark/tools/download_ggufs.sh
#
# Output: the two GGUF files in $MODELS_DIR, with their SHA-256 hashes
# printed at the end (capture these for the InstrumentBundle pin).

set -euo pipefail

MODELS_DIR="${MODELS_DIR:-$HOME/llama.cpp/models}"
mkdir -p "$MODELS_DIR"

# Qwen3-Coder-30B-A3B-Instruct — the headline subject (Phase 5 §"Test subjects").
# Pinned at this harness-build commit to the unsloth GGUF distribution,
# Q4_K_M quant (18.6 GB). Repo: unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF.
# License: Apache-2.0.
QWEN_REPO="unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF"
QWEN_FILE="Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"

# Gemma 4 26B A4B Instruct — the auxiliary judge (Phase 5 pre-reg v7 lock).
# Pinned at this harness-build commit to the unsloth GGUF distribution,
# UD-Q4_K_M quant (16.9 GB; "UD" = Unsloth Dynamic, imatrix-improved).
# Repo: unsloth/gemma-4-26B-A4B-it-GGUF. License: Apache-2.0.
GEMMA_REPO="unsloth/gemma-4-26B-A4B-it-GGUF"
GEMMA_FILE="gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"

echo "[+] destination: $MODELS_DIR"
echo "[+] free disk:   $(df -h "$MODELS_DIR" | awk 'NR==2 {print $4}')"
echo ""

# Skip-if-present discipline: don't re-download if file already exists
# and is non-empty. (HF CLI also dedup's via its cache, but the
# explicit check makes the script idempotent at the shell level.)
download_one() {
    local repo="$1"
    local fname="$2"
    local dest="$MODELS_DIR/$fname"
    if [[ -s "$dest" ]]; then
        echo "[=] $fname already present at $dest ($(du -h "$dest" | cut -f1)); skipping"
        return 0
    fi
    echo "[↓] $repo :: $fname"
    hf download "$repo" "$fname" --local-dir "$MODELS_DIR"
}

download_one "$QWEN_REPO" "$QWEN_FILE"
echo ""
download_one "$GEMMA_REPO" "$GEMMA_FILE"

echo ""
echo "[+] computing SHA-256 hashes for InstrumentBundle / JudgeBundle pinning..."
sha256sum "$MODELS_DIR/$QWEN_FILE" "$MODELS_DIR/$GEMMA_FILE"

echo ""
echo "[+] done. To wire the harness:"
echo ""
echo "    export DRIFTWOOD_QWEN_GGUF_PATH='$MODELS_DIR/$QWEN_FILE'"
echo "    export DRIFTWOOD_GEMMA_GGUF_PATH='$MODELS_DIR/$GEMMA_FILE'"
echo "    export DRIFTWOOD_LLAMA_CPP_BIN='$HOME/llama.cpp/build/bin/llama-server'"
echo ""
