// ---
// tags: trident, rust
// crystal-type: source
// crystal-domain: comp
// ---
use super::analyzer::CostAnalyzer;
use super::model::TableCost;
use trident::ast::*;

// --- Per-function cost result ---

/// Cost analysis result for a single function.

impl<'a> CostAnalyzer<'a> {
    pub(crate) fn cost_expr(&mut self, expr: &Expr) -> TableCost {
        let stack_op = self.cost_model.stack_op();
        match expr {
            Expr::Literal(_) => {
                // push instruction: 1 cc, 1 opstack.
                stack_op
            }
            Expr::Var(_) => {
                // dup instruction: 1 cc, 1 opstack.
                stack_op
            }
            Expr::BinOp { op, lhs, rhs } => {
                let lhs_cost = self.cost_expr(&lhs.node);
                let rhs_cost = self.cost_expr(&rhs.node);
                lhs_cost.add(&rhs_cost).add(&self.cost_model.binop_cost(op))
            }
            Expr::Call { path, args, .. } => {
                let fn_name = path.node.as_dotted();
                let args_cost = args
                    .iter()
                    .fold(TableCost::ZERO, |acc, a| acc.add(&self.cost_expr(&a.node)));

                // Check if it's a builtin — try full name first, then short name
                // to handle cross-module calls like "hash.tip5" → "tip5" → "hash"
                let base_name = fn_name.rsplit('.').next().unwrap_or(&fn_name);
                let fn_cost = {
                    let c = self.cost_model.builtin_cost(&fn_name);
                    if c.is_nonzero() {
                        c
                    } else {
                        self.cost_model.builtin_cost(base_name)
                    }
                };
                if fn_cost.is_nonzero() {
                    // Builtin: use the cost table.
                    args_cost.add(&fn_cost)
                } else {
                    // User-defined: look up body cost + call overhead.
                    let body_cost = if let Some(func) = self.fn_bodies.get(base_name).cloned() {
                        self.cost_fn(&func)
                    } else {
                        TableCost::ZERO
                    };
                    args_cost
                        .add(&body_cost)
                        .add(&self.cost_model.call_overhead())
                }
            }
            Expr::FieldAccess { expr: inner, .. } => {
                // Evaluate inner struct + dup field elements.
                self.cost_expr(&inner.node).add(&stack_op)
            }
            Expr::Index { expr: inner, .. } => {
                // Evaluate inner array + dup indexed element.
                self.cost_expr(&inner.node).add(&stack_op)
            }
            Expr::StructInit { fields, .. } => {
                fields.iter().fold(TableCost::ZERO, |acc, (_, val)| {
                    acc.add(&self.cost_expr(&val.node))
                })
            }
            Expr::ArrayInit(elems) => elems
                .iter()
                .fold(TableCost::ZERO, |acc, e| acc.add(&self.cost_expr(&e.node))),
            Expr::Tuple(elems) => elems
                .iter()
                .fold(TableCost::ZERO, |acc, e| acc.add(&self.cost_expr(&e.node))),
        }
    }

    /// Find the first loop in a function and return its per-iteration cost + bound.
    pub(crate) fn find_loop_iteration_cost(&mut self, func: &FnDef) -> Option<(TableCost, u64)> {
        if let Some(body) = &func.body {
            for stmt in &body.node.stmts {
                if let Stmt::For {
                    bound,
                    body: loop_body,
                    end,
                    ..
                } = &stmt.node
                {
                    let body_cost = self.cost_block(&loop_body.node);
                    let per_iter = body_cost.add(&self.cost_model.loop_overhead());
                    let iterations = if let Some(b) = bound {
                        *b
                    } else if let Expr::Literal(Literal::Integer(n)) = &end.node {
                        *n
                    } else {
                        1
                    };
                    return Some((per_iter, iterations));
                }
            }
        }
        None
    }

    /// H0004: scan a block for loops where declared bound >> constant end value.
    pub(crate) fn scan_loop_bound_waste(&mut self, fn_name: &str, block: &Block) {
        for stmt in &block.stmts {
            if let Stmt::For {
                end, bound, body, ..
            } = &stmt.node
            {
                // Check if end is a constant and bound is declared
                if let (Some(declared_bound), Expr::Literal(Literal::Integer(end_val))) =
                    (bound, &end.node)
                {
                    if *declared_bound > *end_val * 4 && *declared_bound > 8 {
                        self.loop_bound_waste.push((
                            fn_name.to_string(),
                            *end_val,
                            *declared_bound,
                        ));
                    }
                }
                // Recurse into loop body
                self.scan_loop_bound_waste(fn_name, &body.node);
            }
            // Recurse into if/else blocks
            if let Stmt::If {
                then_block,
                else_block,
                ..
            } = &stmt.node
            {
                self.scan_loop_bound_waste(fn_name, &then_block.node);
                if let Some(eb) = else_block {
                    self.scan_loop_bound_waste(fn_name, &eb.node);
                }
            }
            // Recurse into match arms
            if let Stmt::Match { arms, .. } = &stmt.node {
                for arm in arms {
                    self.scan_loop_bound_waste(fn_name, &arm.body.node);
                }
            }
        }
    }
}

/// Smallest power of 2 >= n.
///
/// Delegates to `field::proof::padded_height` — same formula, different name.
pub(crate) fn next_power_of_two(n: u64) -> u64 {
    trident::field::proof::padded_height(n)
}
