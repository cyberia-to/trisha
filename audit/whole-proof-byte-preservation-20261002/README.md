# Exact retained compiler-proof bytes across Git checkout policies

The three PR22 evidence packages now declare `* -text` in their own directories.
Their prior membership manifests are retained explicitly. Every original member
is unchanged; the current manifest adds only the delivery attributes and their
provenance. Root attributes protect the exact 21 measured bootstrap paths that
these existing checkers hash. Bootstrap content, workflow execution and runtime
limits are unchanged.

`checkout_check.py` performed two actual isolated Git checkouts with
`core.autocrlf=true` and `core.eol=crlf`. Both exercised real conversion: the
unprotected `CLAUDE.md` control acquired exactly CRLF line endings. The first
checkout, with only the three audit-directory attributes, preserved all retained
members but all three evidence checkers rejected the changed bootstrap bytes.
The second checkout also protected the exact bootstrap paths: every historical
member and bootstrap identity matched, and all three unchanged evidence checkers
passed under Python 3.14 with `-B -W error`. Exact commands, staged tree identities,
raw output and receipts are retained in the two case directories.

These are metadata integrity checks. No compiler, prover or verifier was run.
The original Linux7200s failures and successful Linuxv2 runs retain their original
statuses. The existing local byte adopter remains an independent running process.

Reproduce a complete byte-filter check from a clean committed checkout:

```sh
python3 -B -W error audit/whole-proof-byte-preservation-20261002/checkout_check.py \
  "$PWD" "$(git rev-parse HEAD^{tree})" /absolute/new-empty-output-directory
```

The output directory must not already exist. The script creates an isolated
shared-object Git clone, sets only that clone's configuration, performs a real
checkout through Git, and replays the three retained evidence checkers. It does
not modify global Git configuration or the source checkout.
