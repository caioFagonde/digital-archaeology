#!/usr/bin/env bash
set -e

echo "Building Docker image (this will compile the Rust engine in release mode)..."
docker compose build

echo "Starting Digital Archaeology TUI..."
# We use 'run' instead of 'up' to ensure strict TTY attachment for the Textual UI
docker compose run --rm app