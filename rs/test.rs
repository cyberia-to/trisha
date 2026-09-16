//! Bounded, isolated execution of Trident test entries on Triton VM.
use crate::lower::{link, ModuleTasm, StackLowering, TritonLowering};
use std::path::Path;
use triton_vm::prelude::*;

const TEST_BUDGET: u32 = 1_000_000;

pub fn run_tests(input: &Path, target: &str, profile: &str) -> Result<String, String> {
    let package = crate::target::package(target)?;
    package.require_command("test")?;
    let options = crate::lower::compile_options(target, profile)?;
    let diagnostics = |errors: Vec<trident::diagnostic::Diagnostic>| {
        errors
            .into_iter()
            .map(|e| e.message)
            .collect::<Vec<_>>()
            .join("\n")
    };
    let (entry, options) = trident::source_options(input, &options).map_err(diagnostics)?;
    let prepared = trident::prepare_test_programs(&entry, &options).map_err(diagnostics)?;
    let mut report = format!("running {} tests on {target}\n", prepared.tests.len());
    let mut passed = 0;
    let mut failed = 0;
    for test in prepared.tests {
        let tasm = link(
            test.modules
                .into_iter()
                .map(|module| ModuleTasm {
                    module_name: module.name,
                    is_program: module.is_program,
                    tasm: TritonLowering::new().lower(&module.ops).join("\n"),
                })
                .collect(),
        );
        match execute(&tasm, TEST_BUDGET) {
            Ok(()) => {
                passed += 1;
                report.push_str(&format!("  test {} ... ok\n", test.name));
            }
            Err(error) => {
                failed += 1;
                report.push_str(&format!(
                    "  test {} ... FAILED\n    error: {error}\n",
                    test.name
                ));
            }
        }
    }
    report.push_str(&format!(
        "\ntest result: {}. {passed} passed; {failed} failed; {} skipped\n",
        if failed == 0 { "ok" } else { "FAILED" },
        prepared.skipped
    ));
    if failed == 0 {
        Ok(report)
    } else {
        Err(report)
    }
}

fn execute(tasm: &str, budget: u32) -> Result<(), String> {
    let program = Program::from_code(tasm).map_err(|e| format!("invalid test assembly: {e}"))?;
    let mut state = VMState::new(program, PublicInput::default(), NonDeterminism::default());
    while !state.halting {
        if state.cycle_count >= budget {
            return Err(format!("Triton test exhausted its {budget}-cycle budget"));
        }
        state
            .step()
            .map_err(|e| format!("Triton execution failed: {e}"))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn non_terminating_assembly_is_bounded() {
        let error = super::execute("call forever halt forever: recurse", 32).unwrap_err();
        assert!(error.contains("32-cycle budget"), "{error}");
    }
}
