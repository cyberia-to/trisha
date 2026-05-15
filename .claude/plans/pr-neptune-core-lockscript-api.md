# PR: neptune-core — expose LockScript in public API

**Target repo**: Neptune-Crypto/neptune-core  
**Target branch**: master  
**Title**: `feat(neptune-cash): expose LockScript and custom lock script output construction`

---

## Motivation

Currently `neptune-cash` (the public re-export crate) does not expose
`LockScript`, `TypeScript`, or any way to create a `TxOutput` whose lock
script is an arbitrary TASM program. All `TxOutputListBuilder` methods
derive the lock script hash from a `ReceivingAddress`, which is hardwired
to the standard wallet key scheme.

This forces any third-party tool that wants to deploy a custom TASM program
as a Neptune LockScript (e.g. a Triton VM warrior CLI, a language compiler
toolchain, a zkApp framework) to take a full dependency on the `neptune-core`
node crate — pulling in ~200k LOC, LevelDB, the full sync engine, and a
multi-minute compile — just to access `Utxo::new_native_currency(digest)`.

The fix is small: re-export three types and add one builder method.

---

## Proposed API

### Re-exports in `neptune-cash` public surface

Add to `neptune_cash::api::export` (or `neptune_cash::prelude`):

```rust
// Re-exported from neptune_core::transaction::lock_script
pub use neptune_core::transaction::lock_script::LockScript;
pub use neptune_core::transaction::lock_script::LockScriptAndWitness;

// Re-exported from neptune_core::models::blockchain::type_scripts
pub use neptune_core::models::blockchain::type_scripts::TypeScript;
```

### `TxOutputListBuilder::with_lock_script` method

```rust
impl TxOutputListBuilder {
    /// Add an output locked by an arbitrary TASM program.
    ///
    /// `lock_script_hash` is the Triton VM program digest — the hash of
    /// the TASM program that must execute successfully to spend this output.
    /// Compute it with `LockScript::from_program(program).hash()` or
    /// directly from `triton_vm::Program::hash()`.
    ///
    /// `coins` specifies what the output contains. For a pure program
    /// deployment with no associated value, pass an empty slice.
    ///
    /// # Example
    ///
    /// ```rust
    /// use triton_vm::prelude::*;
    /// use neptune_cash::api::export::*;
    ///
    /// let program = triton_program!(push 1 assert halt);
    /// let lock_hash = LockScript::from_program(program).hash();
    ///
    /// let mut builder = TxOutputListBuilder::new();
    /// builder.with_lock_script(lock_hash, NativeCurrencyAmount::zero(), &[]);
    /// ```
    pub fn with_lock_script(
        &mut self,
        lock_script_hash: Digest,
        native_amount: NativeCurrencyAmount,
        extra_coins: &[Coin],
    ) -> &mut Self {
        let mut coins = Vec::new();
        if !native_amount.is_zero() {
            coins.push(NativeCurrency.coins_from_amount(native_amount));
        }
        coins.extend_from_slice(extra_coins);
        let utxo = Utxo::new(lock_script_hash, coins);
        self.outputs.push(TxOutput::no_notification(utxo));
        self
    }
}
```

### `LockScript::from_program` convenience constructor

If not already present:

```rust
impl LockScript {
    /// Construct a LockScript from a Triton VM program.
    pub fn from_program(program: triton_vm::program::Program) -> Self {
        LockScript { program }
    }

    /// The Digest that identifies this program on-chain.
    /// Use this as the `lock_script_hash` in UTXO construction.
    pub fn hash(&self) -> Digest {
        self.program.hash()
    }
}
```

---

## What this enables

A thin client (no neptune-core dependency, only neptune-cash) can:

```rust
use neptune_cash::api::export::*;
use triton_vm::prelude::*;

// 1. Compile a Trident program to TASM (via trident-lang)
let tasm: String = compile_to_tasm(source)?;

// 2. Hash it — this is the on-chain identity
let program = Program::from_code(&tasm)?;
let lock_hash = LockScript::from_program(program).hash();

// 3. Create a tx output locked by this program
let mut builder = TxOutputListBuilder::new();
builder.with_lock_script(lock_hash, NativeCurrencyAmount::zero(), &[]);

// 4. Submit via RPC — no node crate needed
client.record_and_broadcast_transaction(builder.build()).await?;
```

Before this PR, step 3 requires `use neptune_core::...` and a direct
dependency on the full node crate.

---

## Scope and non-goals

This PR does **not**:
- Change any consensus logic
- Change any wire format
- Add wallet integration for custom lock scripts (spending is the caller's responsibility)
- Change how lock scripts are executed during block validation

It **only** makes existing internal types accessible to thin clients through
the public `neptune-cash` re-export surface.

---

## Affected files

| File | Change |
|------|--------|
| `neptune-cash/src/api/export.rs` | add `pub use` for `LockScript`, `LockScriptAndWitness`, `TypeScript` |
| `neptune-cash/src/api/tx_initiation/builder.rs` | add `with_lock_script` method on `TxOutputListBuilder` |
| `neptune-core/src/transaction/lock_script.rs` | add `from_program` and `hash` convenience methods (if absent) |

---

## Alternative considered

**neptune-lockscript** micro-crate: publish a separate crate containing
only `LockScript` + its hash computation, with no node dependencies.
Rejected: introduces a third crate to synchronise with neptune-core
releases. The re-export approach is zero maintenance — the type is already
defined, it just needs to be visible.
