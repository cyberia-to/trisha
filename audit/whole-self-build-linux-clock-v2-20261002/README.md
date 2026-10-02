# Linux full self-build certificate replay

Run `36976540959`, attempt `1`, at Trisha
`142198726fdec26dae87e2f694da2c2252fefb0f` completed all four native Linux x64
jobs successfully. Joy was built from
`dd61df9128f6da1f97d4698f45f154f05312fe51` with Rust 1.89.0 and the unchanged
frozen full C1/C2 compiler inputs. The original 7,200-second producer failures
remain in `../whole-self-build-linux-20261002/`.

The separate v2 profile gives each producer a 14,400-second physical deadline;
each fresh verifier retains the 7,200-second deadline. Logical evaluation,
certificate, memory and storage limits remain the reviewed v2 values. Producer
receipts say `pending-staged`; the separate verifier jobs conclude
`fresh-verified-retained`. Complete proofs are retained as 22 ordered parts in
fixed draft release 389977897. No release or tag was published.

| Generation | Produce seconds | Verify seconds | Producer peak RSS bytes | Verifier peak RSS bytes | Certificate bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1 to C2 | 9310.972607244 | 3546.567935994 | 923697152 | 488964096 | 11977015727 |
| C2 to C3 | 10772.054548568 | 3022.060720632 | 925097984 | 489021440 | 10569174820 |

These measurements come from the actual `prove-artifact` and fresh
`verify-artifact` commands in the original producer/verifier Actions receipts,
retained without alteration in `raw/*.zip`. Both fresh extracted compiler
artifacts are 9,691,488 bytes, SHA256
`76a07c08265bd2ef525164472b6b53ac3f0e6cbbedce3250c4202f40ffba34c8`.
Reported full certificate SHA256 values match the original local pair:

- C1: `80212be832ce0a5caafa69d9dd346ff20d51ce20fc86892f0c7039492619bbb0`
- C2: `4db898cbc5133e0b96c758507d32b62aa82c4f39271cedd949b96d641a67de86`

`check.py` replays the original seven archive identities and every archived
member, exact four-job success, reviewed source/toolchain/command identities,
all observed resource rows, compiler bytes, semantic fields and original
pending/completion transport receipts. It uses byte-identical reviewed helper
functions under `replay-contract/`. Archived source and binaries are data;
the replay performs no network access or compiler/proof execution.

Run `python3 -B -W error audit/whole-self-build-linux-clock-v2-20261002/check.py`.
The retained helper review covers contingent adoption separately. This package
records the actual remote positive runs. Independent complete-part adoption
and the local composite negative-case acceptance remain separate gates; this
package makes no completed SH8 acceptance claim.
