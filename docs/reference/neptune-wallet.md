# Neptune 0.15.1 wallet command contract

Trisha selects `State.network_flag` and passes `NEPTUNE_DATA_DIR`, when set,
as the upstream global `--data-dir`. It does not guess Neptune's OS-specific
wallet paths. `which-wallet --network <network>` is the authority for the actual
existing wallet file. Wallet files must resolve to `<base>/<network>/wallet/wallet.dat`.

Balance, coins, next-address and derivation-index listing require a running node
on the selected RPC port. Address allocation/listing verifies the node's network.
Indexed address derivation is offline:
`nth-receiving-address <index> generation --network <network>`. Only generation
keys are supported by this wrapper. Listing defaults to 100 addresses and accepts
an explicit start/limit, capped at 1000 upstream derivations per invocation.

Create invokes `generate-wallet --network <network>`; import invokes the upstream
interactive `import-seed-phrase --network <network>` with inherited terminal I/O.
Trisha does not accept seed words in command-line arguments, echo them, or label
ordinary wallet status output as a seed phrase. Both operations refuse an existing
wallet and require a newly discoverable regular wallet file afterwards; upstream
exit code zero alone is not evidence of successful creation/import.

Remove first discovers the selected wallet with `which-wallet`. It requires
`--confirm`, rejects relative/traversing paths, wrong network/path shapes and
symlink components, and removes only that wallet directory. It does not remove
the blockchain or wallet database. Stop the node before local wallet changes;
import may also require moving its existing wallet database using upstream tools.
Hidden-address preferences are stored separately for each network in Trisha's
configuration directory. No command in this implementation's tests uses a real
wallet or node: tests substitute `neptune-cli` and temporary directories.

`TRISHA_CONFIG_DIR` overrides the preference directory on every platform.
Otherwise Windows uses `%APPDATA%/trisha`, falling back to
`%USERPROFILE%/AppData/Roaming/trisha`; macOS uses
`$HOME/Library/Application Support/trisha`; Linux uses
`$XDG_CONFIG_HOME/trisha` or `$HOME/.config/trisha`. Empty environment values
are ignored. If no usable platform directory exists, use the OS temporary
directory plus `trisha`. These preferences contain no wallet or seed material.
