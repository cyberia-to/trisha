# Build a coordinated local candidate entirely from an extracted source archive.
def executable [name: string] {
    if $nu.os-info.name == windows { $"($name).exe" } else { $name }
}
def build [manifest: path, package: string, log: path] {
    print $"Building ($package) from ($manifest)"
    let result = (^cargo build --manifest-path $manifest --release --locked -p $package | complete)
    $"($result.stdout)($result.stderr)" | save --force $log
    if $result.exit_code != 0 { error make {msg: $"build failed; see ($log)\n($result.stderr)"} }
    if ($result.stderr | lines | any {|line| $line | str starts-with 'warning:' }) {
        error make {msg: $"build emitted warnings; see ($log)"}
    }
}

def main [source: path, prefix: path] {
    let source = ($source | path expand)
    let verifier = ($env.FILE_PWD | path join verify-source.py)
    let checked_prefix = (^python3 $verifier --check-destination $source $prefix | complete)
    if $checked_prefix.exit_code != 0 { error make {msg: $checked_prefix.stderr} }
    let prefix = ($checked_prefix.stdout | str trim)
    if not ($source | path join sources.json | path exists) { error make {msg: "source provenance is missing"} }
    # Validate before creating any destination or invoking Cargo.
    let initial = (^python3 $verifier $source | complete)
    if $initial.exit_code != 0 { error make {msg: $initial.stderr} }
    let destination = $prefix
    let temporary = (if $nu.os-info.name == windows {
        {stdout: (mktemp -d --tmpdir-path ($destination | path dirname) $"(($destination | path basename)).building.XXXXXX"), stderr: '', exit_code: 0}
    } else { ^mktemp -d $"($destination).building.XXXXXX" | complete })
    let prefix = ($temporary.stdout | str trim)
    let owned_staging = (($prefix | str starts-with $"($destination).building.") and (($prefix | path dirname) == ($destination | path dirname)))
    try {
    if $temporary.exit_code != 0 { error make {msg: $"cannot create private candidate staging directory: ($temporary.stderr)"} }
    if not $owned_staging or ($prefix | path type) != dir { error make {msg: "mktemp did not return the expected staging directory"} }
    cd $source
    $initial.stdout | save ($prefix | path join source-verification.json)
    mkdir ($prefix | path join bin)
    $env.CARGO_TARGET_DIR = ($prefix | path join build)
    for project in [trident trisha joy] {
        let manifest = ($source | path join $project Cargo.toml)
        let metadata = (^cargo metadata --manifest-path $manifest --format-version 1 --all-features --locked | complete)
        if $metadata.exit_code != 0 { error make {msg: $metadata.stderr} }
        let packages = ($metadata.stdout | from json | get packages)
        if $project in [trisha joy] {
            for dependency in [triton-vm triton-air triton-isa triton-constraint-circuit triton-constraint-builder tasm-lib tasm-object-derive] {
                let versions = ($packages | where name == $dependency | get version | uniq)
                if $versions != ['7.0.0'] {
                    error make {msg: $"($project): release requires ($dependency)7.0.0; resolved ($versions | str join ', ')"}
                }
            }
        }
        let local = ($packages | where source == null | get manifest_path)
        let contained = (^python3 $verifier --check-contained $source ...$local | complete)
        if $contained.exit_code != 0 { error make {msg: $contained.stderr} }
    }
    build ($source | path join trident Cargo.toml) trident-lang ($prefix | path join trident-build.log)
    build ($source | path join trisha Cargo.toml) trisha ($prefix | path join trisha-build.log)
    build ($source | path join joy Cargo.toml) cyber-joy ($prefix | path join joy-build.log)
    for name in [trident trident-lsp trisha joy] {
        let file = (executable $name)
        cp ($prefix | path join build release $file) ($prefix | path join bin $file)
    }
    # A small fixture helper links to the archived BBG implementation. It creates
    # complete public certificates instead of embedding opaque stale state roots.
    let helper = ($source | path join trisha scripts fixtures Cargo.toml)
    let fixtures = ($prefix | path join share trisha-release-smoke)
    let generated = (^cargo run --manifest-path $helper --release --locked --offline -- $fixtures | complete)
    $"($generated.stdout)($generated.stderr)" | save ($prefix | path join fixture-build.log)
    if $generated.exit_code != 0 { error make {msg: $generated.stderr} }
    if ($generated.stderr | lines | any {|line| $line | str starts-with 'warning:' }) { error make {msg: "fixture build emitted warnings"} }
    let binaries = ([trident trident-lsp trisha joy] | each {|name|
        let path = ($prefix | path join bin (executable $name))
        {name: $name, sha256: (open --raw $path | hash sha256)}
    })
    let final_check = (^python3 $verifier $source --expect ($prefix | path join source-verification.json) | complete)
    if $final_check.exit_code != 0 { error make {msg: $final_check.stderr} }
    if $final_check.stdout != $initial.stdout { error make {msg: "source provenance changed during build"} }
    let toolchain = (^rustc -vV | complete)
    if $toolchain.exit_code != 0 { error make {msg: $toolchain.stderr} }
    {schema_version: 2, platform: $nu.os-info, toolchain: $toolchain.stdout, source: $source, source_verified: true, source_verification_sha256: (open --raw ($prefix | path join source-verification.json) | hash sha256), provenance_sha256: (open --raw ($source | path join sources.json) | hash sha256), binaries: $binaries}
        | to json | save ($prefix | path join candidate.json)
    let publish_check = (^python3 $verifier --check-destination $source $destination | complete)
    if $publish_check.exit_code != 0 { error make {msg: $publish_check.stderr} }
    mv $prefix $destination
    } catch {|failure|
        if $owned_staging and ($prefix | path exists) { rm --recursive --force $prefix }
        error make {msg: $failure.msg}
    }
    print $"Candidate built: ($destination). Run smoke-release.nu against its bin directory. This does not publish a release."
}
