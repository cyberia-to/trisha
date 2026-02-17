#!/usr/bin/env bash
#
# Fetch triton-vm from crates.io and apply GPU acceleration patch.
#
# Usage: ./patches/apply.sh
#
# Result: .vendor/triton-vm/ with GPU hooks ready for use.
# Cargo.toml should point to: triton-vm = { path = ".vendor/triton-vm" }

set -euo pipefail

TRITON_VM_VERSION="2.0.0"
VENDOR_DIR=".vendor/triton-vm"
PATCH_FILE="patches/triton-vm-gpu.patch"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$SCRIPT_DIR"

if [ ! -f "$PATCH_FILE" ]; then
    echo "error: $PATCH_FILE not found" >&2
    exit 1
fi

# Clean previous vendor
rm -rf "$VENDOR_DIR"
mkdir -p .vendor

# Download from crates.io registry cache or cargo download
echo "Fetching triton-vm $TRITON_VM_VERSION..."

# Try cargo's local registry cache first
CARGO_REGISTRY="${CARGO_HOME:-$HOME/.cargo}/registry/src"
CACHED=$(find "$CARGO_REGISTRY" -maxdepth 2 -type d -name "triton-vm-$TRITON_VM_VERSION" 2>/dev/null | head -1)

if [ -n "$CACHED" ] && [ -d "$CACHED" ]; then
    echo "Found cached: $CACHED"
    cp -R "$CACHED" "$VENDOR_DIR"
else
    # Trigger cargo to download it
    echo "Not in cache, downloading via cargo..."
    TEMP_DIR=$(mktemp -d)
    cat > "$TEMP_DIR/Cargo.toml" <<TOML
[package]
name = "fetch-triton-vm"
version = "0.0.0"
edition = "2021"

[dependencies]
triton-vm = "=$TRITON_VM_VERSION"
TOML
    mkdir -p "$TEMP_DIR/src"
    echo "" > "$TEMP_DIR/src/lib.rs"
    (cd "$TEMP_DIR" && cargo fetch 2>/dev/null)
    rm -rf "$TEMP_DIR"

    CACHED=$(find "$CARGO_REGISTRY" -maxdepth 2 -type d -name "triton-vm-$TRITON_VM_VERSION" 2>/dev/null | head -1)
    if [ -z "$CACHED" ]; then
        echo "error: failed to download triton-vm $TRITON_VM_VERSION" >&2
        exit 1
    fi
    cp -R "$CACHED" "$VENDOR_DIR"
fi

# Apply GPU patch
echo "Applying GPU acceleration patch..."
cd "$VENDOR_DIR"
git init -q
git add -A
git commit -q -m "triton-vm $TRITON_VM_VERSION (upstream)"
git apply "../../$PATCH_FILE"
git add -A
git commit -q -m "apply GPU acceleration patch"

echo "Done. Patched triton-vm at $VENDOR_DIR"
echo ""
echo "Set in Cargo.toml:"
echo '  triton-vm = { path = ".vendor/triton-vm" }'
