//! Triton instruction bounds belong to the machine adapter, not shared TIR.
//! Deep access borrows zero RAM cells and clears them before returning. There
//! is no compiler-reserved interval in the source memory address space.

pub(super) fn batch(opcode: &str, count: u32, out: &mut Vec<String>) {
    let mut remaining = count;
    while remaining > 0 {
        let count = remaining.min(5);
        out.push(format!("    {opcode} {count}"));
        remaining -= count;
    }
}

fn emit(lines: &[&str], out: &mut Vec<String>) {
    out.extend(lines.iter().map(|line| format!("    {line}")));
}

pub(super) fn access(depth: u32, duplicate: bool, search: &str, out: &mut Vec<String>) {
    if depth < 16 {
        if duplicate || depth > 0 {
            out.push(format!(
                "    {} {depth}",
                if duplicate { "dup" } else { "swap" }
            ));
        }
        return;
    }
    // Keep as much of the source stack as possible in the native window.
    // Dup needs one pointer register; Swap also loads the previous top word.
    let spilled = depth - if duplicate { 14 } else { 13 };
    let cells = spilled + u32::from(duplicate);
    borrow(cells, search, out);
    batch("write_mem", spilled, out);
    // Stack now holds the untouched prefix and the end pointer.
    if duplicate {
        emit(&["dup 15", "swap 1", "write_mem 1", "push -2", "add"], out);
        restore(spilled, out);
        // Reload the duplicate stored after the original spilled words.
        out.push(format!("    push {cells}"));
        emit(&["add"], out);
        restore(1, out);
    } else {
        emit(&["dup 0"], out);
        out.push(format!("    push -{spilled}"));
        emit(&["add", "read_mem 1", "pop 1", "swap 15", "dup 1"], out);
        out.push(format!("    push -{spilled}"));
        emit(&["add", "write_mem 1", "pop 1", "push -1", "add"], out);
        restore(spilled, out);
    }
    emit(&["pop 1"], out);
}

/// Borrow exactly `cells` verified-zero words; leave their base on the stack.
pub(super) fn borrow(cells: u32, search: &str, out: &mut Vec<String>) {
    // Check a preferred block in batches. It is borrowed only if every cell
    // is zero; occupied blocks fall back to the complete monotonic search.
    // Counting individual zero predicates avoids field-sum cancellation.
    const PREFERRED: u64 = 1 << 31;
    let last = PREFERRED + u64::from(cells) - 1;
    out.push(format!("    push {cells}"));
    out.push(format!("    push {last}"));
    out.push(format!("    push {cells}"));
    emit(&["push 0"], out);
    out.push(format!("    push {last}"));
    let mut remaining = cells;
    while remaining > 0 {
        let chunk = remaining.min(5);
        out.push(format!("    read_mem {chunk}"));
        out.push(format!("    swap {}", chunk + 1));
        for _ in 0..chunk {
            emit(&["swap 1", "push 0", "eq", "add"], out);
        }
        emit(&["swap 1"], out);
        remaining -= chunk;
    }
    emit(&["pop 1"], out);
    out.push(format!("    push {cells}"));
    emit(&["eq", "push 0", "eq", "skiz"], out);
    out.push(format!("    call {search}"));
    // Search returns (required_cells, last_address, run_length).
    emit(&["pop 1", "swap 1", "pop 1"], out);
    out.push(format!("    push {}", 1 - i64::from(cells)));
    emit(&["add"], out);
}

/// Read backwards from the pointer and zero exactly the cells just consumed.
/// The decreasing pointer stays on top of the restored words throughout.
fn restore(mut count: u32, out: &mut Vec<String>) {
    while count > 0 {
        let chunk = count.min(5);
        out.push(format!("    read_mem {chunk}"));
        for _ in 0..chunk {
            emit(&["push 0"], out);
        }
        out.push(format!("    dup {chunk}"));
        emit(&["push 1", "add"], out);
        out.push(format!("    write_mem {chunk}"));
        emit(&["pop 1"], out);
        count -= chunk;
    }
}

/// Find a contiguous zero run without changing RAM. Start at address zero,
/// scan each cell once, and reject field wraparound rather than looping or
/// borrowing an occupied cell. Search cost depends on actual RAM occupancy.
pub(super) fn search(label: &str, out: &mut Vec<String>) {
    out.push(format!("{label}:"));
    // The preferred block was occupied. Discard its end/length and restart at
    // zero. The scanner neither assumes zero-initialized RAM nor writes to it.
    emit(&["pop 2", "push 0", "push 0"], out);
    out.push(format!("    call {label}__scan"));
    emit(&["return"], out);
    scan(&format!("{label}__scan"), out);
}

fn scan(label: &str, out: &mut Vec<String>) {
    out.push(format!("{label}:"));
    emit(
        &[
            // (required, cursor, length) -> (required, cursor, new_length)
            "dup 1",
            "read_mem 1",
            "pop 1",
            "push 0",
            "eq",
            "swap 1",
            "push 1",
            "add",
            "mul",
            // Return before incrementing so a run ending at p-1 is legal.
            "dup 0",
            "dup 3",
            "eq",
            "skiz",
            "return",
            "swap 1",
            "push 1",
            "add",
            "dup 0",
            "push 0",
            "eq",
            "push 0",
            "eq",
            "assert",
            "swap 1",
            "recurse",
        ],
        out,
    );
}

/// Reorder a bounded native ABI window; indices name the original bottom-first words.
pub(super) fn permute(order: &[usize], out: &mut Vec<String>) {
    let mut current: Vec<_> = (0..order.len()).collect();
    let top = order.len() - 1;
    for (position, wanted) in order.iter().enumerate() {
        let found = current
            .iter()
            .position(|x| x == wanted)
            .expect("ABI permutation");
        if position == found {
            continue;
        }
        for index in [found, position, found] {
            if index != top {
                out.push(format!("    swap {}", top - index));
                current.swap(top, index);
            }
        }
    }
}

pub(super) fn reverse(width: usize, out: &mut Vec<String>) {
    permute(&(0..width).rev().collect::<Vec<_>>(), out);
}

#[cfg(test)]
mod tests;
