# Exercise installed compiler + CPU warrior binaries from an empty directory.
# Includes public Zheng certificates; does not certify ZK, recursive proofs, or live deployment.
def checked [binary: path, args: list<string>, expected: int = 0] {
    let result = (^$binary ...$args | complete)
    if $result.exit_code != $expected {
        error make {msg: $"($binary) ($args | str join ' '): exit ($result.exit_code), expected ($expected)\n($result.stderr)"}
    }
    $result
}

def main [bin: path, work: path] {
    let bin = ($bin | path expand)
    let work = ($work | path expand)
    if ($work | path exists) { error make {msg: "work directory must not exist"} }
    mkdir $work
    cd $work
    $env.PATH = [$bin]
    hide-env -i TRIDENT_STDLIB TRIDENT_OSLIB TRIDENT_EXTLIB
    let trident = ($bin | path join trident)
    let trisha = ($bin | path join trisha)
    let joy = ($bin | path join joy)
    checked $trident [--version] | get stdout | print
    checked $trisha [--version] | get stdout | print

    "program portable\nuse vm.core.convert\nuse os.neptune.xfield\nfn main() { let x = pub_read()\n pub_write(convert.as_field(convert.as_u32(x * 7 + 3))) }\n" | save main.tri
    "[project]\nname = \"portable\"\nentry = \"main.tri\"\ntarget = \"neptune\"\n" | save trident.toml
    checked $trident [check main.tri --target neptune] | ignore
    checked $trident [check main.tri --target triton] 1 | ignore
    checked $trident [build .] | ignore
    checked $trisha [build .] | ignore
    if not ("main.tasm" | path exists) { error make {msg: "project build did not produce main.tasm"} }
    let neptune = (checked $trisha [describe --target neptune] | get stdout | from json)
    let triton = (checked $trisha [describe --target triton] | get stdout | from json)
    if $neptune.terrain.digest_width != 5 or $triton.runtime.deploy { error make {msg: "incorrect Triton capabilities"} }
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
    let original = (open --raw main.proof.toml)
    let altered = ($original | str replace 'public_output = ["38"]' 'public_output = ["39"]')
    if $original == $altered { error make {msg: "tamper fixture did not change"} }
    $altered | save --force main.proof.toml
    checked $trident [verify main.proof.toml --target neptune] 1 | ignore

    "program witness\nfn main() { let a = pub_read()\n let b: Field = divine()\n pub_write(a + b) }\n" | save witness.tri
    let secret_run = (checked $trident [run witness.tri --input-values 5 --secret 7])
    if ($secret_run.stdout | str trim) != "12" { error make {msg: "wrong secret input output"} }
    checked $trident [run witness.tri --input-values 5] 1 | ignore
    checked $trisha [prove batch main.tri witness.tri --target neptune --input-values 5 --secret 7 --output proofs] | ignore
    checked $trisha [verify batch proofs/main.proof.toml proofs/witness.proof.toml --target neptune] | ignore
    checked $trisha [deploy main.tri] 1 | ignore
    checked $trisha [build main.tri --target misspelled] 1 | ignore

    "program arithmetic\nfn main(x: Field) -> Field { x * 7 + 3 }\n" | save arithmetic.tri
    let nox_run = (checked $trident [run arithmetic.tri --target nox --input-values 5])
    if ($nox_run.stdout | str trim) != "38" { error make {msg: "wrong nox output"} }
    checked $trident [check arithmetic.tri --target nox] | ignore
    checked $trident [build arithmetic.tri --target nox] | ignore
    checked $trident [package arithmetic.tri --target nox --output packaged/nox] | ignore
    if (glob packaged/nox/*/program.nox | length) != 1 { error make {msg: "nox package extension is incorrect"} }
    checked $trident [prove arithmetic.tri --target nox --input-values 5 --output arithmetic.zheng] | ignore
    checked $trident [verify arithmetic.zheng --target nox] | ignore
    checked $joy [verify arithmetic.zheng --claim 38 --input-values 5] | ignore
    checked $joy [verify arithmetic.zheng --claim 39 --input-values 5] 1 | ignore
    "program bare\nfn main() { pub_write(7) }\n" | save bare.tri
    checked $trident [check bare.tri --target triton] | ignore
    checked $trident [package bare.tri --target triton --output packaged/triton] | ignore
    if (glob packaged/triton/*/program.tasm | length) != 1 { error make {msg: "Triton package extension is incorrect"} }
    "program tests\nfn main() {}\n#[test]\nfn fails() { assert(false) }\n" | save tests.tri
    checked $trident [test tests.tri --target nox] 1 | ignore
    print "PASS: installed Trident/Trisha/Joy packages, target selection, owned Neptune states, artifact extensions, execution/proving/verification, tamper rejection and unsupported recursive SDK rejection."
    print "The Zheng certificate is public and bounded; ZK, recursive proof verification and live deployment remain unavailable."
}
