use crate::cost::stack_verifier;

pub(super) fn candidates(
    assembly: &[String],
    seed: u64,
    variants: usize,
    max_swaps: usize,
) -> Vec<Vec<String>> {
    let mut rng = Xorshift64::new(seed);
    let mut output = equivalent_substitutions(assembly);
    for _ in 0..variants {
        if let Some(candidate) = random_walk_tasm(assembly, max_swaps, &mut rng) {
            output.push(candidate);
        }
    }
    output
}

// ─── TASM Random Walk ─────────────────────────────────────────────

/// Apply random adjacent swaps to TASM, keeping only valid variants.
///
/// Strategy: try swapping adjacent instructions. If the result passes
/// `verify_equivalent()` on multiple random inputs, accept the swap.
fn random_walk_tasm(
    tasm: &[String],
    max_attempts: usize,
    rng: &mut Xorshift64,
) -> Option<Vec<String>> {
    if tasm.len() < 2 {
        return None;
    }

    let mut current = tasm.to_vec();
    let mut changed = false;

    for _ in 0..max_attempts {
        let i = (rng.next() % (current.len() - 1) as u64) as usize;

        // Skip swaps that would reorder dependent instructions
        if instructions_are_independent(&current[i], &current[i + 1]) {
            current.swap(i, i + 1);

            // Verify equivalence on 3 random seeds
            let valid = (0..3u64).all(|trial| {
                let seed = rng.next() ^ trial.wrapping_mul(0x9E3779B97F4A7C15);
                stack_verifier::verify_equivalent(tasm, &current, seed)
            });

            if valid {
                changed = true;
            } else {
                // Revert
                current.swap(i, i + 1);
            }
        }
    }

    if changed {
        Some(current)
    } else {
        None
    }
}

/// Check if two TASM instructions are likely independent (can be reordered).
///
/// Conservative: returns true only for pure stack ops that don't depend
/// on each other's outputs (both push to different stack positions).
fn instructions_are_independent(a: &str, b: &str) -> bool {
    let a_parts: Vec<&str> = a.split_whitespace().collect();
    let b_parts: Vec<&str> = b.split_whitespace().collect();

    if a_parts.is_empty() || b_parts.is_empty() {
        return false;
    }

    let a_op = a_parts[0];
    let b_op = b_parts[0];

    // Two push instructions are always independent
    if a_op == "push" && b_op == "push" {
        return true;
    }

    // Commutative binary ops followed by another commutative op
    // Actually, this is tricky. Be very conservative:
    // Only allow swapping two instructions that both only push (no pops).
    let a_pure_push = matches!(a_op, "push" | "divine" | "read_io");
    let b_pure_push = matches!(b_op, "push" | "divine" | "read_io");

    if a_pure_push && b_pure_push {
        return true;
    }

    // Two nops
    if a_op == "nop" || b_op == "nop" {
        return true;
    }

    false
}

// ─── Equivalent Substitutions ─────────────────────────────────────

/// Apply pattern-based equivalent substitutions to TASM.
///
/// Returns all valid single-substitution variants.
fn equivalent_substitutions(tasm: &[String]) -> Vec<Vec<String>> {
    let mut variants = Vec::new();

    for i in 0..tasm.len() {
        // Single-instruction substitutions
        match tasm[i].as_str() {
            "nop" => {
                // nop → (remove)
                let mut v = tasm.to_vec();
                v.remove(i);
                if verify_substitution(tasm, &v) {
                    variants.push(v);
                }
            }
            "push 0" if i + 1 < tasm.len() && tasm[i + 1] == "add" => {
                // push 0; add → (remove both — identity)
                let mut v = tasm.to_vec();
                v.remove(i + 1);
                v.remove(i);
                if verify_substitution(tasm, &v) {
                    variants.push(v);
                }
            }
            "push 1" if i + 1 < tasm.len() && tasm[i + 1] == "mul" => {
                // push 1; mul → (remove both — identity)
                let mut v = tasm.to_vec();
                v.remove(i + 1);
                v.remove(i);
                if verify_substitution(tasm, &v) {
                    variants.push(v);
                }
            }
            "dup 0" if i + 1 < tasm.len() && tasm[i + 1] == "pop 1" => {
                // dup 0; pop 1 → (remove both — noop)
                let mut v = tasm.to_vec();
                v.remove(i + 1);
                v.remove(i);
                if verify_substitution(tasm, &v) {
                    variants.push(v);
                }
            }
            "swap 1" if i + 1 < tasm.len() && tasm[i + 1] == "swap 1" => {
                // swap 1; swap 1 → (remove both — identity)
                let mut v = tasm.to_vec();
                v.remove(i + 1);
                v.remove(i);
                if verify_substitution(tasm, &v) {
                    variants.push(v);
                }
            }
            _ => {}
        }

        // Expansion substitutions (make longer but equivalent)
        if tasm[i] == "add" && i >= 1 {
            // add → swap 1; add (commutativity — same result)
            let mut v = tasm.to_vec();
            v.insert(i, "swap 1".to_string());
            if verify_substitution(tasm, &v) {
                variants.push(v);
            }
        }

        if tasm[i] == "mul" && i >= 1 {
            // mul → swap 1; mul (commutativity — same result)
            let mut v = tasm.to_vec();
            v.insert(i, "swap 1".to_string());
            if verify_substitution(tasm, &v) {
                variants.push(v);
            }
        }
    }

    variants
}

/// Verify that a substituted TASM sequence is equivalent to the original.
fn verify_substitution(original: &[String], candidate: &[String]) -> bool {
    // Test on 3 different random seeds
    (0..3).all(|seed| stack_verifier::verify_equivalent(original, candidate, seed * 7919 + 42))
}

// ─── PRNG ─────────────────────────────────────────────────────────

/// Simple xorshift64 PRNG for reproducible augmentation.
struct Xorshift64 {
    state: u64,
}

impl Xorshift64 {
    fn new(seed: u64) -> Self {
        Self {
            state: seed | 1, // ensure non-zero
        }
    }

    fn next(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn random_walk_preserves_equivalence() {
        let tasm = vec![
            "push 3".to_string(),
            "push 4".to_string(),
            "add".to_string(),
        ];
        let mut rng = Xorshift64::new(42);
        // Might or might not produce a variant (depends on RNG)
        let result = random_walk_tasm(&tasm, 10, &mut rng);
        if let Some(ref variant) = result {
            // Must be equivalent
            assert!(stack_verifier::verify_equivalent(&tasm, variant, 0));
        }
    }
    #[test]
    fn equivalent_substitutions_are_valid() {
        let tasm = vec!["push 0".to_string(), "add".to_string()];
        let variants = equivalent_substitutions(&tasm);
        for variant in &variants {
            assert!(
                stack_verifier::verify_equivalent(&tasm, variant, 42),
                "substitution not equivalent: {:?}",
                variant,
            );
        }
    }
    #[test]
    fn push_0_add_removed() {
        let tasm = vec![
            "push 5".to_string(),
            "push 0".to_string(),
            "add".to_string(),
        ];
        let variants = equivalent_substitutions(&tasm);
        // Should find the push 0; add → remove variant
        let has_shorter = variants.iter().any(|v| v.len() < tasm.len());
        assert!(has_shorter, "expected push 0; add to be removed");
    }
    #[test]
    fn swap_1_swap_1_eliminated() {
        let tasm = vec![
            "push 1".to_string(),
            "push 2".to_string(),
            "swap 1".to_string(),
            "swap 1".to_string(),
            "add".to_string(),
        ];
        let variants = equivalent_substitutions(&tasm);
        let has_shorter = variants.iter().any(|v| v.len() < tasm.len());
        assert!(has_shorter, "swap 1; swap 1 should be eliminated");
    }
}
