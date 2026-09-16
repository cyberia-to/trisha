// ---
// tags: trident, rust
// crystal-type: source
// crystal-domain: comp
// ---
//! Triton VM lowering — produces TASM from TIR.

use super::StackLowering;
use trident::tir::TIROp;

/// A deferred subroutine block collected during lowering.
struct DeferredBlock {
    label: String,
    ops: Vec<TIROp>,
    /// If true, this is a "then" branch: pop the flag on entry, push 0 on exit.
    clears_flag: bool,
    /// If true, this is a loop body — has its own return/recurse, skip auto-return.
    is_loop: bool,
}

/// Triton VM lowering — produces TASM from IR.
///
/// Structural control flow (`IfElse`, `IfOnly`, `Loop`) is lowered to
/// Triton's deferred-subroutine pattern with `skiz` + `call` branching.
#[derive(Default)]
pub struct TritonLowering {
    /// Collected deferred blocks (flushed after each function).
    deferred: Vec<DeferredBlock>,
    /// Label counter for generating unique deferred block labels.
    label_counter: u32,
    /// One RAM-preserving scratch search subroutine per lowered module.
    scratch_search: Option<String>,
}

impl TritonLowering {
    pub fn new() -> Self {
        Self::default()
    }

    fn fresh_label(&mut self, prefix: &str) -> String {
        self.label_counter += 1;
        format!("__{}__{}", prefix, self.label_counter)
    }

    /// Format a plain label name into Triton's label format.
    fn format_label(&self, name: &str) -> String {
        format!("__{}", name)
    }

    /// Lower a single TIROp to output lines, collecting deferred blocks.
    fn lower_op(&mut self, op: &TIROp, out: &mut Vec<String>) {
        match op {
            // ── Stack ──
            TIROp::Push(v) => out.push(format!(
                "    push {}",
                triton_vm::prelude::BFieldElement::new(*v).value()
            )),
            TIROp::Pop(n) => super::legalize::batch("pop", *n, out),
            TIROp::Dup(d) => self.stack_access(*d, true, out),
            TIROp::Swap(d) => self.stack_access(*d, false, out),

            // ── Arithmetic ──
            TIROp::Add => out.push("    add".to_string()),
            TIROp::Sub => {
                out.push("    push -1".to_string());
                out.push("    mul".to_string());
                out.push("    add".to_string());
            }
            TIROp::Mul => out.push("    mul".to_string()),
            TIROp::Neg => {
                out.push("    push -1".to_string());
                out.push("    mul".to_string());
            }
            TIROp::Eq => out.push("    eq".to_string()),
            TIROp::Lt => out.push("    lt".to_string()),
            TIROp::And => out.push("    and".to_string()),
            TIROp::Or => out.push("    or".to_string()),
            TIROp::Xor => out.push("    xor".to_string()),
            TIROp::DivMod => out.push("    div_mod".to_string()),
            TIROp::Shl => {
                // multiply by 2^n: push 2; pow; mul
                out.push("    push 2".to_string());
                out.push("    pow".to_string());
                out.push("    mul".to_string());
            }
            TIROp::Shr => {
                // TIR has (value, shift); native div_mod wants the numerator
                // on top and returns (quotient, remainder). Keep the quotient.
                out.push("    push 2".to_string());
                out.push("    pow".to_string());
                out.push("    swap 1".to_string());
                out.push("    div_mod".to_string());
                out.push("    pop 1".to_string());
            }
            TIROp::Invert => out.push("    invert".to_string()),
            TIROp::Split => out.push("    split".to_string()),
            TIROp::Log2 => out.push("    log_2_floor".to_string()),
            TIROp::Pow => {
                // TIR passes (base, exponent); Triton pow consumes base on top.
                out.push("    swap 1".to_string());
                out.push("    pow".to_string());
            }
            TIROp::PopCount => out.push("    pop_count".to_string()),

            // ── Recursion — extension field & FRI ──
            TIROp::ExtMul => out.push("    xb_mul".to_string()),
            TIROp::ExtInvert => {
                // Source XField tuples put their last coefficient on top;
                // Triton native extension elements put coefficient zero there.
                out.extend(["    swap 2", "    x_invert", "    swap 2"].map(str::to_owned));
            }
            TIROp::FoldExt | TIROp::FoldBase => {
                // Preserve both top-of-stack RAM pointers while reversing the
                // three accumulator coefficients at depths 2 through 4.
                out.extend(["    swap 2", "    swap 4", "    swap 2"].map(str::to_owned));
                out.push(
                    if matches!(op, TIROp::FoldExt) {
                        "    xx_dot_step"
                    } else {
                        "    xb_dot_step"
                    }
                    .into(),
                );
                out.extend(["    swap 2", "    swap 4", "    swap 2"].map(str::to_owned));
            }

            // ── Recursion — proof verification block ──
            TIROp::ProofBlock { program_hash, body } => {
                out.push(format!("    // proof_block {}", program_hash));
                for body_op in body {
                    self.lower_op(body_op, out);
                }
                out.push("    // end proof_block".to_string());
            }

            // ── I/O ──
            TIROp::ReadIo(n) => super::legalize::batch("read_io", *n, out),
            TIROp::WriteIo(n) => super::legalize::batch("write_io", *n, out),
            TIROp::Hint(n) => super::legalize::batch("divine", *n, out),

            // ── Memory ──
            TIROp::ReadMem(n) => super::legalize::batch("read_mem", *n, out),
            TIROp::WriteMem(n) => super::legalize::batch("write_mem", *n, out),

            // ── Crypto ──
            TIROp::Hash { .. } => {
                super::legalize::reverse(10, out);
                out.push("    hash".into());
                super::legalize::reverse(5, out);
            }
            TIROp::SpongeInit => out.push("    sponge_init".to_string()),
            TIROp::SpongeAbsorb => {
                super::legalize::reverse(10, out);
                out.push("    sponge_absorb".into());
            }
            TIROp::SpongeSqueeze => {
                out.push("    sponge_squeeze".into());
                super::legalize::reverse(10, out);
            }
            TIROp::SpongeLoad => {
                // Native instruction overwrites four stack words and returns an advanced pointer.
                out.extend(
                    [
                        "    push 0",
                        "    push 0",
                        "    push 0",
                        "    push 0",
                        "    swap 4",
                        "    sponge_absorb_mem",
                        "    pop 5",
                    ]
                    .map(str::to_string),
                );
            }
            TIROp::MerkleStep => {
                super::legalize::reverse(5, out);
                out.push("    merkle_step".into());
                super::legalize::reverse(5, out);
            }
            TIROp::MerkleLoad => {
                // Native layout has an unused word between pointer and index.
                out.push("    push 0".into());
                super::legalize::permute(&[6, 7, 0, 5, 4, 3, 2, 1], out);
                out.push("    merkle_step_mem".into());
                super::legalize::permute(&[2, 7, 6, 5, 4, 3, 0, 1], out);
                out.push("    pop 1".into());
            }

            // ── Assertions ──
            TIROp::Assert(1) => out.push("    assert".to_string()),
            TIROp::Assert(_) => out.push("    assert_vector".to_string()),

            // ── Abstract operations (Triton lowering) ──
            TIROp::Reveal {
                tag, field_count, ..
            } => {
                // TIR payload is bottom-first declaration order; native output
                // consumes its first word from the top.
                if *field_count > 1 {
                    super::legalize::reverse(*field_count as usize, out);
                }
                out.push(format!("    push {}", tag));
                out.push("    write_io 1".to_string());
                for _ in 0..*field_count {
                    out.push("    write_io 1".to_string());
                }
            }
            TIROp::Seal {
                tag, field_count, ..
            } => {
                // Triton: pad to rate=10, hash, write 5-element digest.
                let padding = 9usize.saturating_sub(*field_count as usize);
                for _ in 0..padding {
                    out.push("    push 0".to_string());
                }
                out.push(format!("    push {}", tag));
                // Hash preimage: tag, flattened declaration-order words, zeros.
                // Native hash reads its first input from the top.
                let count = *field_count as usize;
                let order = (count..9)
                    .chain((0..count).rev())
                    .chain([9])
                    .collect::<Vec<_>>();
                super::legalize::permute(&order, out);
                out.push("    hash".to_string());
                out.push("    write_io 5".to_string());
            }
            TIROp::RamRead { width } => {
                // Abstract block addresses name the first ascending RAM cell.
                if *width > 1 {
                    out.push(format!("    push {}", width - 1));
                    out.push("    add".into());
                }
                super::legalize::batch("read_mem", *width, out);
                out.push("    pop 1".into());
                super::legalize::reverse(*width as usize, out);
            }
            TIROp::RamWrite { width } => {
                // Native write consumes pointer then the first coordinate on top.
                super::legalize::reverse(*width as usize + 1, out);
                super::legalize::batch("write_mem", *width, out);
                out.push("    pop 1".into());
            }
            // ── Control flow (flat) ──
            TIROp::TargetCall {
                name,
                inputs,
                outputs,
            } => super::target_call::emit(name, *inputs, *outputs, out),
            TIROp::Call(label) => {
                let formatted = if label.starts_with("__") || label.starts_with("@") {
                    // Already prefixed (__) or cross-module (@) — pass through
                    label.clone()
                } else {
                    self.format_label(label)
                };
                out.push(format!("    call {}", formatted));
            }
            TIROp::Return => out.push("    return".to_string()),
            TIROp::Halt => out.push("    halt".to_string()),

            // ── Control flow (structural) ──
            TIROp::IfElse {
                then_body,
                else_body,
            } => {
                let then_label = self.fresh_label("then");
                let else_label = self.fresh_label("else");

                out.push("    push 1".to_string());
                out.push("    swap 1".to_string());
                out.push("    skiz".to_string());
                out.push(format!("    call {}", then_label));
                out.push("    skiz".to_string());
                out.push(format!("    call {}", else_label));

                self.deferred.push(DeferredBlock {
                    label: then_label,
                    ops: then_body.clone(),
                    clears_flag: true,
                    is_loop: false,
                });
                self.deferred.push(DeferredBlock {
                    label: else_label,
                    ops: else_body.clone(),
                    clears_flag: false,
                    is_loop: false,
                });
            }
            TIROp::IfOnly { then_body } => {
                let then_label = self.fresh_label("then");

                out.push("    skiz".to_string());
                out.push(format!("    call {}", then_label));

                self.deferred.push(DeferredBlock {
                    label: then_label,
                    ops: then_body.clone(),
                    clears_flag: false,
                    is_loop: false,
                });
            }
            TIROp::Loop { label, body } => {
                let formatted_label = if label.starts_with("__") {
                    label.clone()
                } else {
                    self.format_label(label)
                };
                self.deferred.push(DeferredBlock {
                    label: formatted_label,
                    ops: body.clone(),
                    clears_flag: false,
                    is_loop: true,
                });
            }

            // ── Program structure ──
            TIROp::FnStart(name) => {
                let formatted = if name.starts_with("__") {
                    name.clone()
                } else {
                    self.format_label(name)
                };
                out.push(format!("{}:", formatted));
            }
            TIROp::FnEnd => {
                out.push("    ".to_string());
                self.flush_deferred(out);
            }
            TIROp::EntryParameters(leaves) => super::entry::emit(leaves, out),
            TIROp::Entry(main_label) => {
                let formatted = if main_label.starts_with("__") {
                    main_label.clone()
                } else {
                    self.format_label(main_label)
                };
                out.push(format!("    call {}", formatted));
                out.push("    halt".to_string());
                out.push(String::new());
            }

            // ── Passthrough ──
            TIROp::Comment(text) => {
                out.push(format!("    // {}", text));
            }
            TIROp::Asm { lines, .. } => {
                for line in lines {
                    let trimmed = line.trim();
                    if !trimmed.is_empty() {
                        out.push(format!("    {}", trimmed));
                    }
                }
            }
        }
    }

    fn ensure_scratch_search(&mut self) {
        if self.scratch_search.is_none() {
            self.scratch_search = Some(self.fresh_label("stack_scratch"));
        }
    }

    fn lower_ops(&mut self, mut ops: &[TIROp], out: &mut Vec<String>) {
        while let Some((first, rest)) = ops.split_first() {
            if let Some(plan) = super::sequence::Shuffle::plan(ops) {
                self.ensure_scratch_search();
                plan.emit(self.scratch_search.as_deref().unwrap_or(""), out);
                ops = &ops[plan.consumed..];
            } else {
                self.lower_op(first, out);
                ops = rest;
            }
        }
    }

    fn stack_access(&mut self, depth: u32, duplicate: bool, out: &mut Vec<String>) {
        if depth >= 16 {
            self.ensure_scratch_search();
        }
        super::legalize::access(
            depth,
            duplicate,
            self.scratch_search.as_deref().unwrap_or(""),
            out,
        );
    }

    /// Flush all deferred blocks, emitting them as labeled subroutines.
    fn flush_deferred(&mut self, out: &mut Vec<String>) {
        while !self.deferred.is_empty() {
            let blocks = std::mem::take(&mut self.deferred);
            for block in blocks {
                out.push(format!("{}:", block.label));

                if block.is_loop {
                    // Loop: counter check, decrement, body, recurse
                    out.push("    dup 0".to_string());
                    out.push("    push 0".to_string());
                    out.push("    eq".to_string());
                    out.push("    skiz".to_string());
                    out.push("    return".to_string());
                    out.push("    push -1".to_string());
                    out.push("    add".to_string());

                    self.lower_ops(&block.ops, out);

                    out.push("    recurse".to_string());
                    out.push(String::new());
                } else {
                    if block.clears_flag {
                        out.push("    pop 1".to_string());
                    }

                    self.lower_ops(&block.ops, out);

                    if block.clears_flag {
                        out.push("    push 0".to_string());
                    }
                    out.push("    return".to_string());
                    out.push(String::new());
                }
            }
        }
    }
}

impl StackLowering for TritonLowering {
    fn lower(&self, ops: &[TIROp]) -> Vec<String> {
        let mut lowerer = TritonLowering::new();
        let mut out = Vec::new();

        lowerer.lower_ops(ops, &mut out);
        if let Some(label) = lowerer.scratch_search {
            // A module's functions terminate explicitly. The barrier also
            // allows standalone flat TIR programs to terminate before helpers.
            out.push("    halt".into());
            super::legalize::search(&label, &mut out);
        }
        out
    }
}
