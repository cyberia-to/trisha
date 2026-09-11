# Build a standalone source tree from committed local dependencies and patched Triton sources.
# Strict default requires committed build inputs. --snapshot-worktrees preserves
# an explicitly marked local candidate, including dirty dependency sources and hashes.
# Neither mode publishes, commits, or changes dependency worktrees.
def main [output: path, --snapshot-worktrees] {
    let repo = ($env.FILE_PWD | path dirname)
    let workspace = ($repo | path dirname)
    let output = ($output | path expand)
    if ($output | path exists) { error make {msg: $"output already exists: ($output)"} }
    let manifests = [($repo | path join Cargo.toml) ($workspace | path join joy Cargo.toml)]
    let packages = ($manifests | each {|manifest|
        let result = (^cargo metadata --manifest-path $manifest --format-version 1 --all-features --locked | complete)
        if $result.exit_code != 0 { error make {msg: $result.stderr} }
        $result.stdout | from json | get packages
    } | flatten)
    let repos = ($packages | where source == null | get manifest_path | each {|p|
        $p | path relative-to $workspace | path split | first
    } | uniq | sort)
    let commits = ($repos | each {|name|
        let dir = ($workspace | path join $name)
        let changes = ((^git -C $dir diff --name-only HEAD | lines)
            | append (^git -C $dir ls-files --others --exclude-standard | lines)
            | where {|p|
            (($p | path parse | get extension) in [rs tri toml nu wgsl msl c h txt json py]) or ($p == "Cargo.lock" and $name in [trisha joy trident])
        })
        if not $snapshot_worktrees and ($changes | is-not-empty) { error make {msg: $"uncommitted source in ($name): ($changes | str join ', ')"} }
        {repository: $name, commit: (^git -C $dir rev-parse HEAD | str trim)}
    })
    mkdir $output
    let provenance = ($commits | each {|item|
        let destination = ($output | path join $item.repository)
        mkdir $destination
        if $snapshot_worktrees {
            let snapshot = (^python3 ($repo | path join scripts snapshot-source.py) ($workspace | path join $item.repository) $destination | complete)
            if $snapshot.exit_code != 0 { error make {msg: $snapshot.stderr} }
            $snapshot.stdout | from json
        } else {
            ^git -C ($workspace | path join $item.repository) archive $item.commit | ^tar -xf - -C $destination
            if $env.LAST_EXIT_CODE != 0 { error make {msg: $"archive failed: ($item.repository)"} }
            $item | insert mode committed
        }
    })
    for required in [trident/src/config/target/mod.rs trident/src/config/target/package.rs trident/src/config/target/discover.rs trisha/cli/build.rs trisha/bundle.rs joy/targets/nox/capabilities.json] {
        if not ($output | path join $required | path exists) {
            error make {msg: $"source archive is missing required build input: ($required)"}
        }
    }
    # Workspace patches are build inputs. Registry dependency patches do not travel
    # through cargo publish, so the source distribution carries the actual source.
    cp -r ($repo | path join .vendor) ($output | path join trisha .vendor)
    $provenance | to json | save ($output | path join sources.json)
    let inventory = (^python3 ($repo | path join scripts snapshot-source.py) --inventory ($output | path join trisha .vendor) | complete)
    if $inventory.exit_code != 0 { error make {msg: $inventory.stderr} }
    $inventory.stdout | save ($output | path join vendor-sources.json)
    "Build all binaries from this archive:\n  cargo build --manifest-path trident/Cargo.toml --release --locked\n  cargo build --manifest-path trisha/Cargo.toml --release --locked -p trisha\n  cargo build --manifest-path joy/Cargo.toml --release --locked -p cyber-joy\nInstall into one prefix:\n  cargo install --path trident --locked --root <prefix>\n  cargo install --path trisha/cli --locked --root <prefix>\n  cargo install --path joy/cli --locked --root <prefix>\nCompiler, machine contracts, SDK modules, network/state data, and Joy capability metadata are embedded. Root workspace lockfiles govern each build.\n" | save ($output | path join BUILD.txt)
    let archive = $"($output).tar.gz"
    ^tar -czf $archive -C ($output | path dirname) ($output | path basename)
    if $env.LAST_EXIT_CODE != 0 { error make {msg: "source archive failed"} }
    print {archive: $archive, sha256: (open --raw $archive | hash sha256)}
}
