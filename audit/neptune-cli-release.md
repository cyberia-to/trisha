# Neptune wallet CLI release correction

Pinned source reviewed: Neptune v0.15.1 at
`/tmp/trisha-neptune-policy-v0.15.1`, especially
`neptune-core-cli/src/command/wallet.rs`, `neptune-core-cli/src/main.rs`,
`neptune-primitives/src/data_directory.rs` and
`neptune-wallet/src/wallet_file.rs`. The executable contract is documented in
`docs/reference/neptune-wallet.md` before implementation.

## Corrected behavior

- Offline indexed addresses receive index, `generation` key type and selected
  network. Generation is the only wrapper-supported key type. All upstream
  commands forward NEPTUNE_DATA_DIR as the global --data-dir option.
- RPC wallet operations use the selected port and verify the node network before
  balance, coins, address allocation or address-list lookup. Indexed derivation
  itself does not require a node or RPC port.
- Create/import use the selected network, refuse an existing wallet, and require
  an actual new wallet.dat reported by which-wallet. Upstream exit0 can mean no
  import occurred; this now fails instead of reporting success.
- Import launches upstream import-seed-phrase with inherited terminal streams.
  Legacy positional seed words are rejected with a generic message, without
  echoing the words or spawning upstream. No seed is passed by Trisha in argv,
  captured output or log messages. Generate output is ordinary status, never
  mislabeled as a seed phrase.
- Which-wallet provides the actual wallet path. Removal validates the absolute
  `<base>/<network>/wallet/wallet.dat` shape, existing regular file, absence of
  symlink components and (for absolute overrides) the selected data-directory
  boundary. It rechecks the selected path immediately before deletion and keeps
  --confirm mandatory. Only the wallet directory is removed, not sibling
  networks, blockchain storage or wallet database. Relative upstream project
  directory behavior is not guessed from stale OS-directory documentation.
- Listing has explicit --start and --limit (default100, maximum1000). It derives
  at most limit addresses even if the remote last index is u64::MAX; checked
  addition terminates at the integer boundary. The upstream index is the last
  used index (wallet key counter minus1), so the endpoint remains inclusive.
- Hidden-address preferences are separated by network.

Mining HTTP methods and the existing successful-exit/offline-node diagnostic
handling were preserved. No real wallet/node process is part of verification:
all tests replace neptune-cli via a temporary PATH and supply temporary data and
configuration directories.

## Validation

`cargo check -p trisha --locked` passed after the wallet migration. Process mock
tests cover exact argv/network/data-directory mapping; unsupported key rejection;
bounded listing and wrong-node network rejection; create/import success and
false-success exit0; interactive stdin and absence of seed echo; confirmation;
wrong-network and symlink deletion refusal; network-scoped hidden preferences.
The existing node_status regression runs alongside these tests.

Release process tests passed: eight wallet tests and the existing node-status
regression, using `cargo test -p trisha --release --locked --test neptune_wallet
--test node_status`. The additional path-authority test removes NEPTUNE_DATA_DIR
and checks that the returned upstream path is used without platform guesses.
This report does not claim full live wallet or network validation.

## Deliberate limits

The wrapper delegates seed validation and the terminal dialog to pinned upstream
Neptune; it does not implement wallet cryptography. Stop a node before offline
wallet modification. Import can still reject when an old wallet database remains;
this wrapper deliberately does not delete that database to force an import.
Filesystem checks reduce accidental/wrong-network deletion; they are not an
atomic capability-based defense against another same-user process concurrently
replacing ancestor directories. No live node integration test or real wallet
mutation was performed or authorized for this task.
