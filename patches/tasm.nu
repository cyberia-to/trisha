#!/usr/bin/env nu
# Published Triton7-compatible recursive verifier with upstream soundness fixes.
let project_root = ($env.FILE_PWD | path join "..")
cd $project_root
mkdir .vendor
for name in [tasm-lib tasm-object-derive] {
    let version = "7.0.0"
    ^python3 -B patches/fetch.py $name $version $".vendor/($name)"
    if $env.LAST_EXIT_CODE != 0 { error make {msg: $"verified recursive source fetch failed: ($name)"} }
}
let manifest = ".vendor/tasm-lib/Cargo.toml"
let original = (open --raw $manifest)
let anchor = "crate-type = [\n    \"cdylib\",\n    \"rlib\",\n]"
if not ($original | str contains $anchor) { error make {msg: "review changed tasm-lib crate types"} }
$original | str replace $anchor 'crate-type = ["rlib"]' | save -f $manifest
print "Pinned tasm-lib7.0.0 installed with upstream security fixes."
