//! Triton instruction bounds belong to the machine adapter, not shared TIR.
//! Deep stack access reserves RAM [2^31, 2^31 + depth + 1); compiler spill
//! and temporary RAM use the disjoint 2^30 and 2^29 regions respectively.
const SCRATCH: u64 = 1 << 31;

pub(super) fn batch(opcode: &str, count: u32, out: &mut Vec<String>) {
    let mut remaining = count;
    while remaining > 0 {
        let count = remaining.min(5);
        out.push(format!("    {opcode} {count}"));
        remaining -= count;
    }
}

fn store(index: u32, out: &mut Vec<String>) {
    out.push(format!("    push {}", SCRATCH + u64::from(index)));
    out.push("    write_mem 1".into());
    out.push("    pop 1".into());
}

fn load(index: u32, out: &mut Vec<String>) {
    out.push(format!("    push {}", SCRATCH + u64::from(index)));
    out.push("    read_mem 1".into());
    out.push("    pop 1".into());
}

pub(super) fn access(depth: u32, duplicate: bool, out: &mut Vec<String>) {
    if depth < 16 {
        if duplicate || depth > 0 {
            out.push(format!(
                "    {} {depth}",
                if duplicate { "dup" } else { "swap" }
            ));
        }
        return;
    }
    if duplicate {
        for index in 0..depth {
            store(index, out);
        }
        out.push("    dup 0".into());
        store(depth, out);
        for index in (0..depth).rev() {
            load(index, out);
        }
        load(depth, out);
    } else {
        for index in 0..=depth {
            store(index, out);
        }
        load(0, out);
        for index in (1..depth).rev() {
            load(index, out);
        }
        load(depth, out);
    }
}
