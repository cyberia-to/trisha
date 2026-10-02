# Complete certificate byte-equivalence retention

The independent readback run
[37047053221](https://github.com/cyberia-to/trisha/actions/runs/37047053221),
attempt 1, passed at Trisha
`97795590613e625b6be43c5e73afff4ab87009cd`. It read all 22 canonical parts,
reconstructed both complete SHA256 values, and retained its original metadata
as Actions artifact `11245008879`. The subsequent local closure passed and
published two unique metadata files to existing draft release `389977897`.
The draft remained unpublished, its tag absent, and the default reference
unchanged in the recorded guards.

SH8 adversarial and final-checker acceptance remains separate. This delivery
records complete transport byte equality and local observations surrounding
the remote readback.

## Actual observations

The command was `python -B -W error scripts/whole_readback/worker.py` in the
reviewed workflow at the revision above. Its original receipt records 356 GET
commands, including 22 complete body reads. The worker elapsed time was
1097.223283822 seconds; sampled worker/child peak RSS was 104816640 bytes.
These are physical observations from that command, with the exact profile
retained alongside them.

| Original generation | Parts | Complete certificate bytes | SHA256 |
| --- | ---: | ---: | --- |
| C1 produces C2 | 12 | 11977015727 | `80212be832ce0a5caafa69d9dd346ff20d51ce20fc86892f0c7039492619bbb0` |
| C2 produces C3 | 10 | 10569174820 | `4db898cbc5133e0b96c758507d32b62aa82c4f39271cedd949b96d641a67de86` |

The authenticated original Actions ZIP is 96198407 bytes, SHA256
`a30b4ebc05220eb0180773bd039570c22b6a44bce2f60471cbef38808ee50edc`.
Its bounded metadata archive contains 732 members and 127091012 decoded bytes.
The independent retained-data replay authenticated every original member,
the six original producer/verifier/pending ZIPs, all body observations and
the final guards. It performed no further network or proof execution.

The local `scripts/whole_readback/local.py after` command used `--run
37047053221 --head 97795590613e625b6be43c5e73afff4ab87009cd` and the exact
independent review SHA
`aecf6561b5d46510ac05567d4a10b7f5f49277e2b759cb479933dbc1a50e58f9`.
The retained wrapper records its complete argv, working directory and exit 0.
Both complete local scans passed: before SHA `77227a12…`, after SHA `1019c533…`.
Their full identities and contents are bound into the equivalence manifest.
The actual closure contains 50 command records, including unique-name guards,
uploads and complete independent readbacks.

| Retained file | Asset | Bytes | SHA256 |
| --- | ---: | ---: | --- |
| Original local metadata | 606256958 | 27321578 | `302a493dd270352b62f52eb306471c3c55ee59ec414ec694b215636b2402a449` |
| Byte-equivalence manifest | 606263560 | 1802711 | `f06ad9892327f4db456a15797e5f49f9d029453e5c5585d036c1f8f4eb9a7adb` |

## Provenance and scope

The original local executions used Joy
`6e0ec4d8440e2521df08f442d64f54e667044716`. The original Linux producer/fresh
verifier run `36976540959` used Joy
`dd61df9128f6da1f97d4698f45f154f05312fe51`, through Trisha
`142198726fdec26dae87e2f694da2c2252fefb0f`. Those execution receipts remain
distinct. The later readback proves equality of the complete retained bytes.
The original failed local adopter remains failed and is referenced by its
original identity. The two local scans are observations before and after the
remote job, rather than continuous filesystem attestation.

The certificates disclose the complete public witness. This transport result
adds no private-relation, succinctness, semantic-preservation, physical-proof
or release-promotion claim. Publication/version decisions remain separate.

## Retained packet and replay

`retention.json` maps each selected original to its exact stored and decoded
identities. JSON originals use deterministic gzip without changing decoded
bytes. `result.json` is a checked summary of the original receipts. The packet
retains the 38-file source closure, source and activation reviews, original
test logs, earlier review findings, actual closure/worker/packing observations,
and the root and independent acceptance drivers and receipts.

`references-only.json` preserves identities for omitted originals. Raw host
process snapshots, signed URLs, private replay extraction and complete proof
bodies are excluded from this public packet. The existing draft assets retain
the actual proof parts and metadata. The retained private replay driver needs
the original local evidence paths; it is never executed by this checker.

From the repository root:

```sh
python3 -B -W error audit/whole-retention-byte-closure/check.py
python3 -B -W error -m unittest discover -s audit/whole-retention-byte-closure -p test_delivery.py -v
```

Where the original local selected files still exist, add `--originals` to
compare every decoded copy against them. The portable checker validates the
selected inventory, privacy rules, source/review bindings and derived result;
the separate original full metadata replay remains bound by its receipt.
Local `.gitattributes` preserves every audit byte under CRLF checkout.
