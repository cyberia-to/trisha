# Build a standalone source tree from committed local dependencies and patched Triton sources.
# Run after the coordinated code commits and lockfile update; this does not publish anything.
def main [output: path] {
    let repo = ($env.FILE_PWD | path dirname)
    let workspace = ($repo | path dirname)
    let output = ($output | path expand)
    if ($output | path exists) { error make {msg: $"output already exists: ($output)"} }
    let metadata = (^cargo metadata --manifest-path ($repo | path join Cargo.toml) --format-version 1 --all-features --locked | from json)
    let repos = ($metadata.packages | where source == null | get manifest_path | each {|p|
        $p | path relative-to $workspace | path split | first
    } | uniq | sort)
    let commits = ($repos | each {|name|
        let dir = ($workspace | path join $name)
        let changes = ((^git -C $dir diff --name-only HEAD | lines)
            | append (^git -C $dir ls-files --others --exclude-standard | lines)
            | where {|p|
            ($p | path parse | get extension) in [rs tri toml nu wgsl msl c h]
        })
        if ($changes | is-not-empty) { error make {msg: $"uncommitted source in ($name): ($changes | str join ', ')"} }
        {repository: $name, commit: (^git -C $dir rev-parse HEAD | str trim)}
    })
    mkdir $output
    for item in $commits {
        let destination = ($output | path join $item.repository)
        mkdir $destination
        ^git -C ($workspace | path join $item.repository) archive $item.commit | ^tar -xf - -C $destination
        if $env.LAST_EXIT_CODE != 0 { error make {msg: $"archive failed: ($item.repository)"} }
    }
    # Workspace patches are build inputs. Registry dependency patches do not travel
    # through cargo publish, so the source distribution carries the actual source.
    cp -r ($repo | path join .vendor) ($output | path join trisha .vendor)
    $commits | to json | save ($output | path join sources.json)
    "Build: cd trisha; cargo build --release --locked -p trisha\nInstall: cargo install --path cli --locked --root <prefix>\nThe compiler and Neptune resources are embedded.\n" | save ($output | path join BUILD.txt)
    let archive = $"($output).tar.gz"
    ^tar -czf $archive -C ($output | path dirname) ($output | path basename)
    if $env.LAST_EXIT_CODE != 0 { error make {msg: "source archive failed"} }
    print {archive: $archive, sha256: (open --raw $archive | hash sha256)}
}
