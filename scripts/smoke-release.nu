# Exercise installed compiler + CPU warrior binaries from an empty directory.
# This does not certify Zheng execution proofs or Neptune deployment.
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
    checked $trident [--version] | get stdout | print
    checked $trisha [--version] | get stdout | print

    "program portable\nuse vm.core.convert\nuse os.neptune.xfield\nfn main() { let x = pub_read()\n pub_write(convert.as_field(convert.as_u32(x * 7 + 3))) }\n" | save main.tri
    "[project]\nname = \"portable\"\nentry = \"main.tri\"\ntarget = \"triton\"\n" | save trident.toml
    checked $trident [build .] | ignore
    for binary in [$trident $trisha] {
        let run = (checked $binary [run . --input-values 5])
        if ($run.stdout | str trim) != "38" { error make {msg: "wrong arithmetic output"} }
    }
    checked $trident [prove . --input-values 5 --output main.proof.toml] | ignore
    checked $trident [verify main.proof.toml --target triton] | ignore
    let original = (open --raw main.proof.toml)
    let altered = ($original | str replace 'public_output = ["38"]' 'public_output = ["39"]')
    if $original == $altered { error make {msg: "tamper fixture did not change"} }
    $altered | save --force main.proof.toml
    checked $trident [verify main.proof.toml --target triton] 1 | ignore

    "program witness\nfn main() { let a = pub_read()\n let b: Field = divine()\n pub_write(a + b) }\n" | save witness.tri
    let secret_run = (checked $trident [run witness.tri --input-values 5 --secret 7])
    if ($secret_run.stdout | str trim) != "12" { error make {msg: "wrong secret input output"} }
    checked $trident [run witness.tri --input-values 5] 1 | ignore
    checked $trisha [prove batch main.tri witness.tri --input-values 5 --secret 7 --output proofs] | ignore
    checked $trisha [verify batch proofs/main.proof.toml proofs/witness.proof.toml] | ignore
    checked $trisha [deploy main.tri] 1 | ignore
    checked $trisha [build main.tri --target misspelled] 1 | ignore

    "program arithmetic\nfn main(x: Field) -> Field { x * 7 + 3 }\n" | save arithmetic.tri
    let nox_run = (checked $trident [run arithmetic.tri --target nox --input-values 5])
    if ($nox_run.stdout | str trim) != "38" { error make {msg: "wrong nox output"} }
    "program tests\nfn main() {}\n#[test]\nfn fails() { assert(false) }\n" | save tests.tri
    checked $trident [test tests.tri --target nox] 1 | ignore
    print "PASS: installed compiler/Triton build, execute, prove, verify, tamper rejection, public/secret inputs, batch; nox execution and failing-test exit."
    print "Zheng execution-proof soundness and live deployment remain outside this smoke gate."
}
