# Exercise installed compiler + CPU warrior binaries from an empty directory.
# Exercises actual public/private/state execution artifacts; live deployment remains separate.
def executable [name: string] {
    if $nu.os-info.name == windows { $"($name).exe" } else { $name }
}
def checked [binary: path, args: list<string>, expected: int = 0] {
    let result = (^$binary ...$args | complete)
    if $result.exit_code != $expected {
        error make {msg: $"($binary) ($args | str join ' '): exit ($result.exit_code), expected ($expected)\n($result.stderr)"}
    }
    $result
}

def expect-magic [file: path, expected: string] {
    let header = (open --raw $file | into binary | bytes at 0..7 | decode utf-8)
    if $header != $expected { error make {msg: $"wrong artifact version: ($file): ($header)"} }
}

def binary-hashes [bin: path] {
    [trident trident-lsp trisha joy] | each {|name|
        {name: $name, sha256: (open --raw ($bin | path join (executable $name)) | hash sha256)}
    }
}

def fixture-hashes [fixtures: path] {
    [state.json other-state.json state-all.json] | each {|name|
        {name: $name, sha256: (open --raw ($fixtures | path join $name) | hash sha256)}
    }
}

def main [bin: path, work: path, --fixtures: path] {
    let script_path = ($env.FILE_PWD | path join smoke-release.nu)
    let script_hash = (open --raw $script_path | hash sha256)
    let lsp_script = ($env.FILE_PWD | path join smoke-lsp.py)
    let lsp_script_hash = (open --raw $lsp_script | hash sha256)
    let python = (which python3 | first | get path)
    let bin = ($bin | path expand)
    let work = ($work | path expand)
    let fixtures = ($fixtures | default ($bin | path dirname | path join share trisha-release-smoke) | path expand)
    if ($work | path exists) { error make {msg: "work directory must not exist"} }
    let candidate = (open ($bin | path dirname | path join candidate.json))
    if $candidate.schema_version != 2 { error make {msg: "candidate must include the LSP and native platform identity"} }
    let verification_path = ($bin | path dirname | path join source-verification.json)
    let verification_hash = (open --raw $verification_path | hash sha256)
    if ($candidate.source_verified? | default false) != true or $candidate.source_verification_sha256 != $verification_hash {
        error make {msg: "installed candidate lacks its exact verified source inventory receipt"}
    }
    let binaries = (binary-hashes $bin)
    let fixture_files = (fixture-hashes $fixtures)
    if $candidate.binaries != $binaries or ($candidate.provenance_sha256 | str length) != 64 {
        error make {msg: "installed binaries do not match candidate provenance"}
    }
    mkdir $work
    cd $work
    $env.PATH = [$bin]
    $env.RAYON_NUM_THREADS = ($env.RAYON_NUM_THREADS? | default '4')
    hide-env -i TRIDENT_STDLIB TRIDENT_OSLIB TRIDENT_EXTLIB TRIDENT_TARGET_PACKAGES
    let trident = ($bin | path join (executable trident))
    let trisha = ($bin | path join (executable trisha))
    let joy = ($bin | path join (executable joy))
    checked $python [$lsp_script ($bin | path join (executable trident-lsp))] | get stdout | print
    checked $trident [--version] | get stdout | print
    checked $trisha [--version] | get stdout | print
    checked $joy [--version] | get stdout | print

    "program portable\nuse vm.core.convert\nuse os.neptune.xfield\nfn main() { let x = pub_read()\n pub_write(convert.as_field(convert.as_u32(x * 7 + 3))) }\n" | save main.tri
    "[project]\nname = \"portable\"\nentry = \"main.tri\"\ntarget = \"neptune\"\n" | save trident.toml
    checked $trident [check main.tri --target neptune] | ignore
    checked $trident [check main.tri --target triton] 1 | ignore
    checked $trident [build .] | ignore
    checked $trisha [build .] | ignore
    if not ("main.tasm" | path exists) { error make {msg: "project build did not produce main.tasm"} }
    let neptune = (checked $trisha [describe --target neptune] | get stdout | from json)
    let triton = (checked $trisha [describe --target triton] | get stdout | from json)
    for package in [$neptune $triton] {
        if $package.compiler_api != 3 or $package.schema_version != 1 { error make {msg: "release requires compiler API 3 and target schema 1"} }
    }
    let nox_contract = (checked $joy [describe --target nox] | get stdout | from json)
    if $nox_contract.compiler_api != 3 or $nox_contract.schema_version != 1 { error make {msg: "Joy compiler API or schema mismatch"} }
    if $neptune.terrain.digest_width != 5 or $triton.runtime.deploy { error make {msg: "incorrect Triton capabilities"} }
    if 'stark-triton-v7' not-in $triton.runtime.proof_formats { error make {msg: "release requires the Triton7 proof backend"} }
    for state in $neptune.states {
        let shown = (checked $trisha [state show $state.union $state.name] | get stdout)
        if not ($shown | str contains $state.display_name) { error make {msg: "described state differs from CLI state"} }
    }
    checked $trident [package main.tri --target neptune --output packaged/neptune] | ignore
    checked $trident [package main.tri --target neptune --state unknown --output rejected-state] 1 | ignore
    if (glob packaged/neptune/*/program.tasm | length) != 1 { error make {msg: "Neptune package extension is incorrect"} }
    "program rejected\nuse os.neptune.proof\nfn main() { proof.verify_inner_proof(0) }\n" | save rejected.tri
    checked $trident [check rejected.tri --target neptune] 1 | ignore
    for binary in [$trident $trisha] {
        let run = (checked $binary [run . --input-values 5])
        if ($run.stdout | str trim) != "38" { error make {msg: "wrong arithmetic output"} }
    }
    checked $trident [prove . --input-values 5 --output main.proof.toml] | ignore
    checked $trident [verify main.proof.toml --target neptune] | ignore
    let inspected = (checked $trisha [deploy main.tri --vm neptune --state testnet --rpc-port 19001 --proof main.proof.toml --dry-run] | get stdout | from json)
    if $inspected.format != trisha-neptune-program-plan-v1 or not $inspected.execution_proof_verified or $inspected.rpc_port != 19001 or $inspected.state != testnet or ($inspected.lock_script_hash | length) != 5 or $inspected.submission_supported or $inspected.transaction != null {
        error make {msg: "offline Neptune inspection does not bind the verified program and selected state"}
    }
    let original = (open --raw main.proof.toml)
    $original | save inner.proof.toml
    let altered = ($original | str replace 'public_output = ["38"]' 'public_output = ["39"]')
    if $original == $altered { error make {msg: "tamper fixture did not change"} }
    $altered | save --force main.proof.toml
    checked $trident [verify main.proof.toml --target neptune] 1 | ignore
    checked $trisha [deploy main.tri --vm neptune --proof main.proof.toml --dry-run] 1 | ignore

    # Bind the native program hash from source inspection and explicit expected
    # I/O; the witness adapter must not choose its own authorization claim.
    print "Checking installed Triton recursive execution and outer proof..."
    {schema_version: 1, program_hash: $inspected.lock_script_hash, public_input: ['5'], public_output: ['38']}
        | to json | save expected-inner.json
    checked $trisha [witness inner.proof.toml --expected-claim expected-inner.json --output recursive-witness.json] | ignore
    "program outer\nuse vm.triton.proof\nuse vm.io.io\nfn main() { proof.verify(io.read_digest())\n pub_write(1) }\n" | save outer.tri
    for binary in [$trident $trisha] {
        if (checked $binary [run outer.tri --target triton --input-file recursive-witness.json] | get stdout | str trim) != '1' {
            error make {msg: "installed recursive SDK rejected the expected native proof"}
        }
    }
    let recursive_input = (open recursive-witness.json)
    let changed_commitment = (if $recursive_input.public.0 == '0' { '1' } else { '0' })
    $recursive_input | update public.0 $changed_commitment | to json | save forged-recursive-witness.json
    checked $trisha [run outer.tri --target triton --input-file forged-recursive-witness.json] 1 | ignore
    checked $trident [prove outer.tri --target triton --input-file recursive-witness.json --output outer.proof.toml] | ignore
    checked $trisha [verify outer.proof.toml --target triton] | ignore
    let outer_proof = (open outer.proof.toml)
    if $outer_proof.claim.public_input != $recursive_input.public or $outer_proof.claim.public_output != ['1'] {
        error make {msg: "outer STARK does not expose the complete expected inner claim commitment"}
    }
    $outer_proof | update claim.public_output ['2'] | to toml | save forged-outer.proof.toml
    checked $trisha [verify forged-outer.proof.toml --target triton] 1 | ignore

    "program witness\nfn main() { let a = pub_read()\n let b: Field = divine()\n pub_write(a + b) }\n" | save witness.tri
    let secret_run = (checked $trident [run witness.tri --input-values 5 --secret 7])
    if ($secret_run.stdout | str trim) != "12" { error make {msg: "wrong secret input output"} }
    checked $trident [run witness.tri --input-values 5] 1 | ignore
    checked $trisha [prove batch main.tri witness.tri --target neptune --input-values 5 --secret 7 --output proofs] | ignore
    checked $trisha [verify batch proofs/main.proof.toml proofs/witness.proof.toml --target neptune] | ignore
    checked $trisha [deploy main.tri] 1 | ignore
    checked $trisha [build main.tri --target misspelled] 1 | ignore

    # Typed executable entry must consume input before main, including spilled
    # aggregate words. Exercise source dispatch and default-security proofs.
    "program typed_entry\nfn main(a: Field, b: U32, flag: Bool, words: [Field; 20]) {\n assert(flag)\n assert(words[0] == 101)\n assert(words[1] == 102)\n assert(words[2] == 103)\n assert(words[3] == 104)\n assert(words[4] == 105)\n assert(words[5] == 106)\n assert(words[6] == 107)\n assert(words[7] == 108)\n assert(words[8] == 109)\n assert(words[9] == 110)\n assert(words[10] == 111)\n assert(words[11] == 112)\n assert(words[12] == 113)\n assert(words[13] == 114)\n assert(words[14] == 115)\n assert(words[15] == 116)\n assert(words[16] == 117)\n assert(words[17] == 118)\n assert(words[18] == 119)\n assert(words[19] == 120)\n pub_write(a*100+as_field(b))\n pub_write(pub_read())\n}\n" | save typed-entry.tri
    let entry_input = '7,19,1,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,31'
    for profile in [debug release] {
        for binary in [$trident $trisha] {
            let output = (checked $binary [run typed-entry.tri --target triton --profile $profile --input-values $entry_input] | get stdout | lines)
            if $output != ['719' '31'] { error make {msg: "typed entry lost input order, aggregate leaves or stream remainder"} }
            for invalid in ['7,4294967296,1,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,31' '7,19,2,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,31' '7,19,1,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119'] {
                checked $binary [run typed-entry.tri --target triton --profile $profile --input-values $invalid] 1 | ignore
            }
        }
        let proof = $"typed-entry-($profile).proof.toml"
        checked $trident [prove typed-entry.tri --target triton --profile $profile --input-values $entry_input --output $proof] | ignore
        checked $trisha [verify $proof --target triton] | ignore
        let artifact = (open $proof)
        if $artifact.claim.public_input != ($entry_input | split row ',') or $artifact.claim.public_output != ['719' '31'] {
            error make {msg: "typed entry proof differs from the exact public claim"}
        }
        let altered_input = $"typed-entry-($profile)-bad-input.proof.toml"
        let altered_output = $"typed-entry-($profile)-bad-output.proof.toml"
        $artifact | update claim.public_input.0 '8' | to toml | save $altered_input
        $artifact | update claim.public_output.0 '718' | to toml | save $altered_output
        checked $trident [verify $altered_input --target triton] 1 | ignore
        checked $trisha [verify $altered_output --target triton] 1 | ignore
    }

    # Stack legalization, multiword cleanup and asm must share uncorrupted RAM.
    "program stack_ram_release\nuse vm.io.mem\nfn pair(x: Field) -> (Field, Field) { (x, x + 1) }\nfn main() {\n let words: [Field;20] = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]\n let sentinel = pub_read()\n mem.write(1073741824,1001)\n mem.write(2147483648,999)\n let (x,y) = pair(7)\n asm { push 1073741824 read_mem 1 pop 1 write_io 1 }\n pub_write(words[0])\n pub_write(x)\n pub_write(y)\n pub_write(sentinel)\n pub_write(mem.read(2147483648))\n pub_write(mem.read(1073741824))\n}\n" | save stack-ram.tri
    let ram_expected = ['1001' '1' '7' '8' '97' '999' '1001']
    for profile in [debug release] {
        for binary in [$trident $trisha] {
            let output = (checked $binary [run stack-ram.tri --target triton --profile $profile --input-values 97] | get stdout | lines)
            if $output != $ram_expected { error make {msg: "compiler stack operations corrupted source RAM or named locals"} }
        }
        let proof = $"stack-ram-($profile).proof.toml"
        checked $trident [prove stack-ram.tri --target triton --profile $profile --input-values 97 --output $proof] | ignore
        checked $trisha [verify $proof --target triton] | ignore
        let artifact = (open $proof)
        if $artifact.claim.public_input != ['97'] or $artifact.claim.public_output != $ram_expected {
            error make {msg: "RAM preservation proof differs from the required public claim"}
        }
        let forged = $"stack-ram-($profile)-bad-output.proof.toml"
        $artifact | update claim.public_output.5 '20' | to toml | save $forged
        checked $trisha [verify $forged --target triton] 1 | ignore
    }

    "program arithmetic\nfn helper(x: Field) -> Field { x * 7 + 3 }\nfn main(x: Field) -> Field { helper(x) }\n" | save arithmetic.tri
    let nox_run = (checked $trident [run arithmetic.tri --target nox --input-values 5])
    if ($nox_run.stdout | str trim) != "38" { error make {msg: "wrong nox output"} }
    checked $trident [check arithmetic.tri --target nox] | ignore
    checked $trident [build arithmetic.tri --target nox] | ignore
    let built = (checked $joy [build arithmetic.tri --target nox --profile release --format json-v1] | get stdout | from json)
    if $built.schema != joy/cli/v1 or $built.command != build or not $built.ok or $built.result.target_vm != nox or $built.result.target_package.owner != joy {
        error make {msg: "Joy build does not return the versioned nox artifact identity"}
    }
    let built_run = (checked $joy [run arithmetic.bundle.json --input-values 5] | get stdout | str trim)
    if $built_run != '38' { error make {msg: "installed Joy bundle produced the wrong result"} }
    let bundle_hash = (open --raw arithmetic.bundle.json | hash sha256)
    let refused = (checked $joy [build arithmetic.tri --target nox --format json-v1] 1 | get stdout | from json)
    if $refused.ok or $refused.error.code != artifact_write_failed or (open --raw arithmetic.bundle.json | hash sha256) != $bundle_hash {
        error make {msg: "Joy build failed to preserve an existing artifact"}
    }
    checked $joy [build arithmetic.tri --target nox --emit nox --output joy-built.nox] | ignore
    if (checked $joy [run joy-built.nox --input-values 5] | get stdout | str trim) != '38' { error make {msg: "exported nox artifact produced the wrong result"} }
    checked $trident [package arithmetic.tri --target nox --output packaged/nox] | ignore
    if (glob packaged/nox/*/program.nox | length) != 1 { error make {msg: "nox package extension is incorrect"} }
    checked $trident [prove arithmetic.tri --target nox --input-values 5 --output arithmetic.zheng] | ignore
    expect-magic arithmetic.zheng JOYEXEC2
    checked $trident [verify arithmetic.zheng --target nox] | ignore
    checked $joy [verify arithmetic.zheng --claim 38 --input-values 5] | ignore
    checked $joy [verify arithmetic.bundle.json --proof arithmetic.zheng --claim 38 --input-values 5] | ignore
    checked $joy [verify arithmetic.zheng --claim 39 --input-values 5] 1 | ignore
    checked $joy [verify arithmetic.zheng --claim 38 --input-values 6] 1 | ignore
    "program private_execution\nfn helper(x: Field) -> Field { let witness: Field = divine()\n witness * witness + x }\nfn main(x: Field) -> Field { helper(x) }\n" | save private.tri
    checked $trident [prove private.tri --target nox --input-values 5 --secret 42 --output private.zheng] | ignore
    expect-magic private.zheng JOYZK003
    checked $joy [verify private.zheng --claim 1769 --input-values 5] | ignore
    checked $joy [verify private.tri --target nox --profile release --proof private.zheng --claim 1769] | ignore
    checked $joy [verify private.zheng --claim 1770] 1 | ignore
    checked $joy [verify private.zheng --input-values 6] 1 | ignore
    checked $joy [prove private.tri --target nox --input-values 5 --output missing-secret.zheng] 1 | ignore

    cp ($fixtures | path join state.json) state.json
    cp ($fixtures | path join other-state.json) other-state.json
    cp ($fixtures | path join state-all.json) state-all.json
    "program state_execution\nfn helper(k: Field) -> Field { os.state.read(k) }\nfn main(k: Field) -> Field { helper(k) + 5 }\n" | save state.tri
    let state_run = (checked $joy [run state.tri --target nox --state state.json --input-values 11])
    if ($state_run.stdout | str trim) != "82" { error make {msg: "wrong authenticated state output"} }
    checked $joy [prove state.tri --target nox --state state.json --input-values 11 --output state.zheng] | ignore
    expect-magic state.zheng JOYST001
    checked $joy [verify state.zheng --claim 82 --input-values 11] | ignore
    checked $joy [verify state.tri --target nox --proof state.zheng --state state.json --claim 82] | ignore
    checked $joy [verify state.zheng --claim 83] 1 | ignore
    checked $joy [verify state.zheng --input-values 12] 1 | ignore
    checked $joy [verify state.zheng --state other-state.json] 1 | ignore
    checked $joy [prove state.tri --target nox --state state.json --zk --input-values 11 --output unsupported-private-state.zheng] 1 | ignore

    "program private_state_execution\nfn helper(k: Field) -> Field { os.state.read(k) }\nfn main(x: Field) -> Field { let key: Field = divine()\n helper(key) + x }\n" | save private-state.tri
    checked $joy [prove private-state.tri --target nox --state state-all.json --input-values 5 --secret 11 --output private-state.zheng] | ignore
    expect-magic private-state.zheng JOYZK003
    checked $joy [verify private-state.zheng --claim 82 --input-values 5 --state state-all.json] | ignore
    checked $joy [verify private-state.tri --target nox --proof private-state.zheng --claim 82] | ignore
    checked $joy [verify private-state.zheng --claim 83] 1 | ignore
    checked $joy [verify private-state.zheng --state other-state.json] 1 | ignore

    # nox source entries receive flat words and enforce the complete signature.
    "program typed_nox\nstruct Pair { a: Field, n: U32, flag: Bool }\nfn main(pair: Pair, words: [Field;3], digest: Digest)->Field { assert(pair.flag)\n assert(words[0] == 101)\n assert(words[1] == 103)\n assert(words[2] == 107)\n assert(digest[0] == 307)\n assert(digest[1] == 311)\n assert(digest[2] == 313)\n assert(digest[3] == 317)\n pair.a*100+as_field(pair.n) }\n" | save typed-nox.tri
    let nox_input = '7,19,0,101,103,107,307,311,313,317'
    for profile in [debug release] {
        for binary in [$trident $joy] {
            if (checked $binary [run typed-nox.tri --target nox --profile $profile --input-values $nox_input] | get stdout | str trim) != '719' {
                error make {msg: "nox entry changed aggregate input layout"}
            }
            for invalid in ['7,4294967296,0,101,103,107,307,311,313,317' '7,19,2,101,103,107,307,311,313,317' '7,19,0,101,103,107,307,311,313' '7,19,0,101,103,107,307,311,313,317,1'] {
                checked $binary [run typed-nox.tri --target nox --profile $profile --input-values $invalid] 1 | ignore
            }
        }
        let proof = $"typed-nox-($profile).zheng"
        checked $joy [prove typed-nox.tri --target nox --profile $profile --input-values $nox_input --output $proof] | ignore
        expect-magic $proof JOYEXEC2
        checked $joy [verify $proof --claim 719 --input-values $nox_input] | ignore
        checked $joy [verify $proof --claim 718] 1 | ignore
        checked $joy [verify $proof --input-values '7,19,2,101,103,107,307,311,313,317'] 1 | ignore
    }
    "program typed_private\nfn main(n: U32, flag: Bool)->Field { assert(flag)\n let hidden: Field = divine()\n as_field(n)+hidden }\n" | save typed-private.tri
    checked $joy [prove typed-private.tri --target nox --profile release --input-values '19,0' --secret 23 --output typed-private.zheng] | ignore
    expect-magic typed-private.zheng JOYZK003
    checked $joy [verify typed-private.zheng --claim 42 --input-values '19,0'] | ignore
    checked $joy [verify typed-private.zheng --input-values '4294967296,0'] 1 | ignore
    checked $joy [verify typed-private.zheng --input-values '19,2'] 1 | ignore

    # Bounded return and aggregate shadow scope must agree on both runtimes.
    "program typed_shadow\nstruct Pair { a: Field, b: Field }\nstruct Reverse { b: Field, a: Field }\nfn main(n: Field) -> Field {\n    let x = Pair { a: 11, b: 22 }\n    for i in 0..2 {\n        if n == as_field(i) { return x.a } else {\n            let x = Reverse { b: 99, a: 88 }\n        }\n        if x.a == 22 { return 999 }\n    }\n    x.a\n}" | save loop-shadow.tri
    "program typed_shadow\nstruct Pair { a: Field, b: Field }\nstruct Reverse { b: Field, a: Field }\nfn regression(n: Field) -> Field {\n    let x = Pair { a: 11, b: 22 }\n    for i in 0..2 {\n        if n == as_field(i) { return x.a } else {\n            let x = Reverse { b: 99, a: 88 }\n        }\n        if x.a == 22 { return 999 }\n    }\n    x.a\n}\nfn main(n: Field) { pub_write(regression(n)) }\n" | save loop-shadow-triton.tri
    for profile in [debug release] {
        for input in ['0' '1' '9'] {
            if (checked $joy [run loop-shadow.tri --target nox --profile $profile --input-values $input] | get stdout | str trim) != '11' {
                error make {msg: "nox loop leaked a shadowed aggregate scope"}
            }
            if (checked $trisha [run loop-shadow-triton.tri --target triton --profile $profile --input-values $input] | get stdout | str trim) != '11' {
                error make {msg: "Triton loop differs from the expected source result"}
            }
        }
    }
    "program private_return\nfn main(n: Field) -> Field {\n let witness: Field = divine()\n for i in 0..2 { if as_field(i) == 1 { return witness + n } }\n let unused: Field = divine()\n unused\n}\n" | save loop-private.tri
    checked $joy [prove loop-private.tri --target nox --profile release --input-values 5 --secret 37 --output loop-private.zheng] | ignore
    expect-magic loop-private.zheng JOYZK003
    checked $joy [verify loop-private.zheng --claim 42 --input-values 5] | ignore
    checked $joy [verify loop-private.zheng --claim 43] 1 | ignore
    checked $joy [verify loop-private.zheng --input-values 6] 1 | ignore

    # Imported concrete generics, declaration-order structs and terminal branches.
    "module release_helper\nconst OFFSET:Field=18446744069414584328\npub struct Pair { a:Field,b:Field }\nfn add(x:Field)->Field {x+OFFSET}\npub fn fold<N>(words:[Field;N])->Field {let mut value:Field=0\nfor i in 0..N {value=value*10+words[i]}\nif value==35 {add(value)} else {value}}\npub fn pair()->Pair {Pair {b:19,a:7}}\n" | save release_helper.tri
    "program imported\nuse release_helper\nconst OFFSET:Field=1000\nfn main(words:[Field;2])->Field {let p=release_helper.pair()\nrelease_helper.fold<2>(words)+release_helper.fold(words)+p.a*100+p.b}\n" | save imported-nox.tri
    "program imported\nuse release_helper\nconst OFFSET:Field=1000\nfn main(words:[Field;2]) {let p=release_helper.pair()\npub_write(release_helper.fold<2>(words)+release_helper.fold(words)+p.a*100+p.b)}\n" | save imported-triton.tri
    for profile in [debug release] {
        for vector in [{input: '3,5', output: '803'} {input: '4,5', output: '809'}] {
            for route in [{binary: $trident, source: imported-nox.tri, target: nox} {binary: $joy, source: imported-nox.tri, target: nox} {binary: $trident, source: imported-triton.tri, target: triton} {binary: $trisha, source: imported-triton.tri, target: triton}] {
                if (checked $route.binary [run $route.source --target $route.target --profile $profile --input-values $vector.input] | get stdout | str trim) != $vector.output {
                    error make {msg: "imported generic, terminal branch or struct layout changed the source result"}
                }
            }
        }
    }
    checked $joy [prove imported-nox.tri --target nox --profile release --input-values '3,5' --output imported.zheng] | ignore
    checked $joy [verify imported.zheng --claim 803 --input-values '3,5'] | ignore
    checked $joy [verify imported.zheng --claim 0] 1 | ignore
    checked $joy [verify imported.zheng --input-values '4,5'] 1 | ignore
    checked $trisha [prove imported-triton.tri --target triton --profile release --input-values '3,5' --output imported.proof.toml] | ignore
    checked $trisha [verify imported.proof.toml] | ignore
    let imported_proof = (open imported.proof.toml)
    if $imported_proof.claim.public_input != ['3' '5'] or $imported_proof.claim.public_output != ['803'] {
        error make {msg: "imported generic proof did not bind the expected native input/output"}
    }
    $imported_proof | update claim.public_output ['0'] | to toml | save imported-bad-output.proof.toml
    checked $trisha [verify imported-bad-output.proof.toml] 1 | ignore
    "module broken\npub fn value<N>(words:[Field;N])->Field {true}\n" | save broken.tri
    for invalid in [
        "program invalid\nfn main()->Field {true}"
        "program invalid\nfn main()->U32 {4294967296}"
        "program invalid\nfn main(x:Field)->Field {if x==0 {return 7}}"
        "program invalid\nuse broken\nfn main()->Field {broken.value<2>([7,19])}"
    ] {
        $invalid | save --force invalid-return.tri
        for target in [nox triton] {
            checked $trident [check invalid-return.tri --target $target] 1 | ignore
        }
    }

    "program bare\nfn main() { pub_write(7) }\n" | save bare.tri
    checked $trident [check bare.tri --target triton] | ignore
    checked $trident [package bare.tri --target triton --output packaged/triton] | ignore
    if (glob packaged/triton/*/program.tasm | length) != 1 { error make {msg: "Triton package extension is incorrect"} }
    "program tests\nfn main() {}\n#[test]\nfn fails() { assert(false) }\n" | save tests.tri
    checked $trident [test tests.tri --target nox] 1 | ignore
    "module helper\nfn value() -> Field { 7 }\npub fn checked() -> Field { value() }\n" | save helper.tri
    "program installed_tests\nuse helper\nfn main() { assert(false) }\n#[test]\nfn actual_vm() { assert(helper.checked() == 7) }\n#[cfg(release)]\n#[test]\nfn skipped() { assert(false) }\n" | save installed-tests.tri
    let test_run = (checked $trident [test installed-tests.tri --target triton])
    if not ($test_run.stderr | str contains '1 passed; 0 failed; 1 skipped') { error make {msg: "installed Triton test runner did not execute/count tests"} }
    checked $trident [test installed-tests.tri --target triton --profile release] 1 | ignore
    if (binary-hashes $bin) != $binaries { error make {msg: "installed binaries changed during smoke"} }
    if (fixture-hashes $fixtures) != $fixture_files { error make {msg: "state fixtures changed during smoke"} }
    if (open --raw $verification_path | hash sha256) != $verification_hash { error make {msg: "source verification receipt changed during smoke"} }
    if (open --raw $script_path | hash sha256) != $script_hash { error make {msg: "smoke script changed during execution"} }
    if (open --raw $lsp_script | hash sha256) != $lsp_script_hash { error make {msg: "LSP smoke changed during execution"} }
    {schema_version: 2, suite: 'installed-compiler-warrior-v2', all_checks_passed: true,
     source_provenance_sha256: $candidate.provenance_sha256, binaries: $binaries,
     source_verification_sha256: $verification_hash,
     smoke_script_sha256: $script_hash,
     lsp_script_sha256: $lsp_script_hash,
     fixture_files: $fixture_files, platform: $nu.os-info} | to json | save smoke.json
    print "PASS: installed Trident/Trisha/Joy packages, Joy build, target selection, owned Neptune states, typed entry parameters, loop returns and scope, artifact extensions, execution/proving/verification, recursive Triton outer proof, offline program inspection and tamper rejection."
    print "Public JOYEXEC2, private JOYZK003 and authenticated-public-state JOYST001 paths passed. Private queries use bounded, fully public state tables. Neptune transaction validation and live deployment remain separate gates."
}
