#!/usr/bin/env nu
#
# Fetch triton-vm from crates.io and apply GPU acceleration patches.
#
# Usage: nu patches/apply.nu
#
# Patches are layered — each builds on the previous:
#   00-visibility    Open internal types for external integration
#   01-gpu-trait     GpuAccelerator trait + global registration
#   02-hash-dispatch GPU dispatch for Tip5 batch hashing
#   03-intt-dispatch GPU dispatch for inverse NTT
#
# Result: .vendor/triton-vm/ with GPU hooks ready for use.
# Cargo.toml should point to: triton-vm = { path = ".vendor/triton-vm" }

let version = "2.0.0"
let vendor_dir = ".vendor/triton-vm"
let project_root = ($env.FILE_PWD | path join "..")

cd $project_root

let patches = (glob "patches/*.patch" | sort)

if ($patches | is-empty) {
    error make { msg: "no patches found in patches/" }
}

# Clean previous vendor
rm -rf $vendor_dir
mkdir .vendor

print $"Fetching triton-vm ($version)..."

let cargo_home = ($env | get -o CARGO_HOME | default $"($env.HOME)/.cargo")
let registry_src = $"($cargo_home)/registry/src"
let crate_name = $"triton-vm-($version)"

# Search cargo registry cache
let cached = (glob $"($registry_src)/**/($crate_name)" | first)

if ($cached | is-empty) {
    print "Not in cache, downloading via cargo..."
    let tmp = (mktemp -d)
    $"[package]\nname = \"fetch-triton-vm\"\nversion = \"0.0.0\"\nedition = \"2021\"\n\n[dependencies]\ntriton-vm = \"=($version)\"\n" | save $"($tmp)/Cargo.toml"
    mkdir $"($tmp)/src"
    "" | save $"($tmp)/src/lib.rs"
    cd $tmp
    cargo fetch
    cd $project_root
    rm -rf $tmp

    let cached = (glob $"($registry_src)/**/($crate_name)" | first)
    if ($cached | is-empty) {
        error make { msg: $"failed to download triton-vm ($version)" }
    }
}

print $"Found: ($cached)"
cp -r $cached $vendor_dir

cd $vendor_dir
git init -q
git add -A
git commit -q -m $"triton-vm ($version) \(upstream\)"

# Apply patches in order
for patch in $patches {
    let name = ($patch | path basename)
    print $"  applying ($name)"
    git apply $patch
    git add -A
    # Commit message = first line of the patch file (the description)
    let msg = (open $patch | lines | first)
    git commit -q -m $msg
}

cd $project_root
print $"Done. ($patches | length) patches applied to ($vendor_dir)"
