# Package only the exact installed binaries that completed the full release smoke.
def executable [name: string] {
    if $nu.os-info.name == windows { $"($name).exe" } else { $name }
}
def main [prefix: path, output: path, --smoke: path] {
    let repo = ($env.FILE_PWD | path dirname)
    let prefix = ($prefix | path expand)
    let output = ($output | path expand)
    if ($output | path exists) { error make {msg: "binary archive output must not exist"} }
    if $smoke == null { error make {msg: "--smoke must name a completed installed smoke receipt"} }
    let smoke_path = ($smoke | path expand)
    if not ($smoke_path | path exists) { error make {msg: "installed smoke receipt is missing"} }
    let candidate = (open ($prefix | path join candidate.json))
    let receipt = (open $smoke_path)
    if $candidate.schema_version != 2 or $receipt.schema_version != 2 or $receipt.suite != installed-compiler-warrior-v2 or $receipt.all_checks_passed != true {
        error make {msg: "full installed smoke did not pass"}
    }
    if $receipt.source_provenance_sha256 != $candidate.provenance_sha256 {
        error make {msg: "smoke and candidate source provenance differ"}
    }
    let verification = ($prefix | path join source-verification.json)
    let verification_hash = (open --raw $verification | hash sha256)
    if ($candidate.source_verified? | default false) != true or $candidate.source_verification_sha256 != $verification_hash or $receipt.source_verification_sha256 != $verification_hash {
        error make {msg: "build and smoke must bind the exact source/vendor verification receipt"}
    }
    let source = ($candidate.source | path expand)
    if (open --raw ($source | path join sources.json) | hash sha256) != $candidate.provenance_sha256 {
        error make {msg: "candidate source provenance has changed"}
    }
    let checked_source = (^python3 ($repo | path join scripts verify-source.py) $source --expect $verification | complete)
    if $checked_source.exit_code != 0 { error make {msg: $"candidate source files changed: ($checked_source.stderr)"} }
    let smoke_script = ($source | path join trisha scripts smoke-release.nu)
    if (open --raw $smoke_script | hash sha256) != $receipt.smoke_script_sha256 {
        error make {msg: "tested smoke script differs from verified source archive"}
    }
    let lsp_script = ($source | path join trisha scripts smoke-lsp.py)
    if (open --raw $lsp_script | hash sha256) != $receipt.lsp_script_sha256 {
        error make {msg: "tested LSP smoke differs from verified source archive"}
    }
    let names = [joy trident trident-lsp trisha]
    for recorded in [$candidate.binaries $receipt.binaries] {
        if ($recorded | get name | sort) != $names { error make {msg: "receipt must contain exactly the four release binaries"} }
    }
    for name in $names {
        let actual = (open --raw ($prefix | path join bin (executable $name)) | hash sha256)
        let candidate_hash = ($candidate.binaries | where name == $name | first | get sha256)
        let tested_hash = ($receipt.binaries | where name == $name | first | get sha256)
        if $actual != $candidate_hash or $actual != $tested_hash { error make {msg: $"untested or changed binary: ($name)"} }
    }
    let licenses = [
        {project: trident, file: LICENSE.md}
        {project: trisha, file: LICENSE}
        {project: joy, file: LICENSE}
    ]
    for license in $licenses { open --raw ($source | path join $license.project $license.file) | ignore }
    let fixture_names = [state.json other-state.json state-all.json]
    if ($receipt.fixture_files | get name | sort) != ($fixture_names | sort) { error make {msg: "smoke must bind exactly the three state fixtures"} }
    for name in $fixture_names {
        let actual = (open --raw ($prefix | path join share trisha-release-smoke $name) | hash sha256)
        let tested = ($receipt.fixture_files | where name == $name | first | get sha256)
        if $actual != $tested { error make {msg: $"untested or changed fixture: ($name)"} }
    }
    # Validation precedes staging and archive creation. Fixed archive epoch and
    # normalized tar metadata make identical inputs produce identical bytes.
    let temporary = (if $nu.os-info.name == windows {
        {stdout: (mktemp -d), stderr: '', exit_code: 0}
    } else { ^mktemp -d | complete })
    if $temporary.exit_code != 0 { error make {msg: $"cannot create staging directory: ($temporary.stderr)"} }
    let staging = ($temporary.stdout | str trim)
    if ($staging | is-empty) or not ($staging | path exists) { error make {msg: "mktemp did not create a staging directory"} }
    try {
        mkdir ($staging | path join bin)
        mkdir ($staging | path join share trisha-release-smoke)
        mkdir ($staging | path join licenses)
        for name in $names {
            let file = (executable $name)
            open --raw ($prefix | path join bin $file) | into binary | save ($staging | path join bin $file)
            if $nu.os-info.name != windows {
                let mode = (^chmod 755 ($staging | path join bin $file) | complete)
                if $mode.exit_code != 0 { error make {msg: $"cannot mark binary executable: ($mode.stderr)"} }
            }
            let copied = (open --raw ($staging | path join bin $file) | hash sha256)
            if $copied != ($receipt.binaries | where name == $name | first | get sha256) { error make {msg: $"binary changed during packaging: ($name)"} }
        }
        for name in $fixture_names {
            open --raw ($prefix | path join share trisha-release-smoke $name) | into binary | save ($staging | path join share trisha-release-smoke $name)
            let copied = (open --raw ($staging | path join share trisha-release-smoke $name) | hash sha256)
            if $copied != ($receipt.fixture_files | where name == $name | first | get sha256) { error make {msg: $"fixture changed during packaging: ($name)"} }
        }
        for license in $licenses {
            cp ($source | path join $license.project $license.file) ($staging | path join licenses $"($license.project).txt")
        }
        $candidate | reject source | to json | save ($staging | path join candidate.json)
        cp $verification ($staging | path join source-verification.json)
        if (open --raw ($staging | path join source-verification.json) | hash sha256) != $verification_hash { error make {msg: "source verification receipt changed during packaging"} }
        cp $smoke_script ($staging | path join share trisha-release-smoke smoke-release.nu)
        cp $lsp_script ($staging | path join share trisha-release-smoke smoke-lsp.py)
        if (open --raw ($staging | path join share trisha-release-smoke smoke-lsp.py) | hash sha256) != $receipt.lsp_script_sha256 { error make {msg: "LSP smoke changed during packaging"} }
        if (open --raw ($staging | path join share trisha-release-smoke smoke-release.nu) | hash sha256) != $receipt.smoke_script_sha256 { error make {msg: "smoke script changed during packaging"} }
        $receipt | to json | save ($staging | path join smoke.json)
        "Cyber compiler and warriors — tested local binary candidate\n\nExtract cyber-tools and add its bin directory to PATH. Keep trident, trident-lsp, trisha and joy together. Z3 is an optional dependency for trident audit --z3. Inspect each command with --version and --help. Exact binary SHA256 identities are in candidate.json and smoke.json. The smoke receipt records the tested platform; this archive is not portable to arbitrary OS/CPU combinations.\n\nshare/trisha-release-smoke contains public test certificates, not wallet data. licenses contains the three project licenses.\n\nFull installed compiler/warrior smoke passed for these binary hashes. This includes recursive and public/private/state proof paths; private state tables are bounded and public. Live Neptune admission/deployment, GPU proving, registry publication and universal formal verification are separate gates. This local archive is not a publication or network action.\n" | save ($staging | path join README.txt)
        ^python3 ($repo | path join scripts archive-source.py) $staging $output --epoch 0 --prefix cyber-tools
        if $env.LAST_EXIT_CODE != 0 { error make {msg: "binary archive creation failed"} }
    } catch {|failure|
        rm -rf $staging
        error make {msg: $failure.msg}
    }
    rm -rf $staging
    print {archive: $output, sha256: (open --raw $output | hash sha256)}
}
