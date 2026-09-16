//! Coalesce adjacent pure stack operations into one RAM-preserving shuffle.
use super::legalize;
use trident::tir::TIROp;

pub(super) struct Shuffle {
    pub consumed: usize,
    width: u32,
    /// Original bottom-first input indices, in final bottom-first order.
    order: Vec<u32>,
}

impl Shuffle {
    pub(super) fn plan(ops: &[TIROp]) -> Option<Self> {
        let (mut required, mut balance) = (0i64, 0i64);
        let (mut consumed, mut cost, mut deep) = (0, 0u64, false);
        // These limit optimization work only; larger runs use normal lowering.
        for op in ops.iter().take(1024) {
            let (need, change, op_cost) = match op {
                TIROp::Dup(d) | TIROp::Swap(d) => {
                    let duplicate = matches!(op, TIROp::Dup(_));
                    deep |= *d >= 16;
                    let cost = if *d < 16 {
                        u64::from(duplicate || *d != 0)
                    } else {
                        let cells = u64::from(*d - 13);
                        // Conservative lower bound for an individual access
                        // when its preferred RAM block is free.
                        16 + 5 * cells + 7 * cells.div_ceil(5)
                    };
                    (i64::from(*d) + 1, i64::from(duplicate), cost)
                }
                TIROp::Pop(n) => (i64::from(*n), -i64::from(*n), u64::from(*n).div_ceil(5)),
                _ => break,
            };
            required = required.max(need - balance);
            balance += change;
            if required > 4096 || required + balance > 4096 {
                return None;
            }
            consumed += 1;
            cost += op_cost;
        }
        if !deep || consumed < 2 {
            return None;
        }
        let mut order: Vec<u32> = (0..required as u32).collect();
        for op in &ops[..consumed] {
            match *op {
                TIROp::Dup(depth) => order.push(order[order.len() - 1 - depth as usize]),
                TIROp::Swap(depth) => {
                    let top = order.len() - 1;
                    order.swap(top, top - depth as usize);
                }
                TIROp::Pop(count) => order.truncate(order.len() - count as usize),
                _ => unreachable!("plan contains only pure stack operations"),
            }
        }
        if order.is_empty() {
            return None;
        }
        let mut uses = vec![0usize; required as usize];
        for &index in &order {
            uses[index as usize] += 1;
        }
        // Leave a prefix on the operand stack only when no later output needs
        // to duplicate it. This avoids hiding a still-needed source word.
        let prefix = order
            .iter()
            .enumerate()
            .take_while(|(index, value)| **value as usize == *index && uses[*index] == 1)
            .count();
        let plan = Self {
            consumed,
            width: required as u32 - prefix as u32,
            order: order[prefix..]
                .iter()
                .map(|index| index - prefix as u32)
                .collect(),
        };
        if plan.width == 0 {
            return None;
        }
        let mut candidate = Vec::new();
        plan.emit("__scratch", &mut candidate);
        ((candidate.len() as u64) < cost).then_some(plan)
    }

    pub(super) fn emit(&self, search: &str, out: &mut Vec<String>) {
        legalize::borrow(self.width, search, out);
        legalize::batch("write_mem", self.width, out);
        out.extend([format!("    push -{}", self.width), "    add".into()]);
        // Keep the base on top while reconstructing the entire result. Source
        // words can be loaded multiple times, so clear only after the last use.
        for index in &self.order {
            out.push("    dup 0".into());
            let offset = self.width - 1 - index;
            if offset != 0 {
                out.extend([format!("    push {offset}"), "    add".into()]);
            }
            out.extend([
                "    read_mem 1".into(),
                "    pop 1".into(),
                "    swap 1".into(),
            ]);
        }
        let mut remaining = self.width;
        while remaining > 0 {
            let count = remaining.min(5);
            out.extend((0..count).map(|_| "    push 0".into()));
            out.extend([
                format!("    swap {count}"),
                format!("    write_mem {count}"),
            ]);
            remaining -= count;
        }
        out.push("    pop 1".into());
    }
}
