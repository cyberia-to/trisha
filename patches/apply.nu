#!/usr/bin/env nu
#
# Fetch triton-vm from crates.io and apply GPU acceleration patch.
#
# Usage: nu patches/apply.nu
#
# Result: .vendor/triton-vm/ with GPU hooks ready for use.
# Cargo.toml should point to: triton-vm = { path = ".vendor/triton-vm" }

let version = "2.0.0"
let vendor_dir = ".vendor/triton-vm"
let patch_file = "patches/triton-vm-gpu.patch"
let project_root = ($env.FILE_PWD | path join "..")

cd $project_root

if not ($patch_file | path exists) {
    error make { msg: $"($patch_file) not found" }
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
    # Trigger cargo to download
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

# Apply GPU patch
print "Applying GPU acceleration patch..."
cd $vendor_dir
git init -q
git add -A
git commit -q -m $"triton-vm ($version) \(upstream\)"
git apply $"../../($patch_file)"
git add -A
git commit -q -m "apply GPU acceleration patch"

cd $project_root
print $"Done. Patched triton-vm at ($vendor_dir)"
