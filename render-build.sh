#!/usr/bin/env bash
set -euo pipefail

# Render build helper for projects that need to compile Rust extensions
# (pydantic-core, or other maturin-based wheels).
#
# Usage: set Render's "Build Command" to: bash backend/render-build.sh

echo "Preparing writable cargo directories..."
export CARGO_HOME="$HOME/.cargo"
export RUSTUP_HOME="$HOME/.rustup"
mkdir -p "$CARGO_HOME" "$RUSTUP_HOME"

echo "Installing Rust toolchain (rustup)..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
rustup default stable || true

echo "Upgrading pip and installing maturin..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install maturin

echo "Installing Python dependencies..."
python -m pip install -r requirements.txt

echo "Build script finished."
