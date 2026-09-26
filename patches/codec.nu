# Keep each warrior's locked macro version; only generated error order changes.
for version in [0.7.0 0.7.1] {
    let directory = $".vendor/bfieldcodec_derive-($version)"
    ^python3 -B patches/fetch.py bfieldcodec_derive $version $directory
    if $env.LAST_EXIT_CODE != 0 { error make {msg: "verified codec macro fetch failed"} }
    let file = ($directory | path join src lib.rs)
    let source = (open --raw $file)
    if (($source | split row 'HashMap' | length) != 4) {
        error make {msg: "review changed codec macro map anchors"}
    }
    $source | str replace --all 'HashMap' 'BTreeMap'
        | append '
#[cfg(test)]
#[path = "determinism_tests.rs"]
mod determinism_tests;
'
        | str join '' | save -f $file
    cp patches/codec_determinism_tests.rs ($directory | path join src determinism_tests.rs)
    # The upstream crate has its own unit tests, runnable independently.
    '
[workspace]
' | save --append ($directory | path join Cargo.toml)
}
