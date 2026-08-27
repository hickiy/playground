#!/bin/bash

# Quick CPU demo run for MNIST training/eval.
# Run as:
# bash run.sh

set -euo pipefail

# All the setup stuff
export PROJECT_BASE_DIR="$HOME/.recognition_handwritten_digital"
mkdir -p "$PROJECT_BASE_DIR"/datasets
mkdir -p "$PROJECT_BASE_DIR"/checkpoints

command -v uv &> /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
[ -d ".venv" ] || uv venv
uv sync
source .venv/bin/activate

# Train + eval + test
python mnist_pipeline.py \
    --data-root "$PROJECT_BASE_DIR/datasets" \
    --dataset-name mnist \
    --model-name mlp \
    --save-dir "$PROJECT_BASE_DIR/checkpoints"
