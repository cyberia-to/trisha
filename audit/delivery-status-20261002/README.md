# Delivery status observation — 2026-10-02

This documentation correction starts from Trisha
`95899e8f4fe32b5d7269d92b5e63ef429fbfafac`, the PR24 merge into `release/0.4`.
The [package audit](../final-host-ceiling-package/README.md) retains the actual
gate evidence for source archive
`73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8`.
Updating these status pointers changes no runtime, selector, package or prior
validation receipt.

At `2026-10-02T19:42:22.124234+00:00`, this single read-only request observed
the integration/default references, the exact `v0.3.0` tag and at most ten
release records:

```sh
gh api graphql --input audit/delivery-status-20261002/request.json
```

The original [response](response.json), [request](request.json),
[stderr](stderr.log) and [command receipt](receipt.json) are retained unchanged.
The response reports complete pagination for this bounded query and:

- Published release `390026240`, tag `v0.3.0`, at `2026-09-16T18:21:24Z`;
  the tag and release both identify commit
  `ba5fca686c81dbf4c5cd1970b309553b0d875b14`.
- Existing draft `389977897`, with no publication timestamp or tag commit,
  used to retain the separately scoped current rehearsal evidence.
- `release/0.4` at `95899e8f4fe32b5d7269d92b5e63ef429fbfafac` and `master`
  at `3cb3984eca9e6a1e71cb9fd8e2cc7ea18913fd2d`.

This observation establishes publication history at that instant. It neither
changes a reference nor establishes SH8 acceptance or a new public release.
The old pre-release index remains explicitly historical. Product versions,
registry packaging and public promotion retain their separate owner workflow.
