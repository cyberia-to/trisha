//! Capture the VM-authenticated initial program digest, before source execution.
const ADDRESS: u64 = super::witness::CONTROL_ADDRESS + 320;
pub const ENTRYPOINT: &str = "trisha_program_digest";

pub fn prologue() -> String {
    // Triton OpStack::new places reversed program digest below eleven zeroes.
    // Capture each word separately so the original stack and depths stay intact.
    (0..5)
        .map(|i| {
            format!(
                "    dup {}\n    push {}\n    write_mem 1\n    pop 1\n",
                11 + i,
                ADDRESS + i
            )
        })
        .collect()
}
pub fn assembly() -> String {
    let mut result = format!("{ENTRYPOINT}:\n");
    for i in 0..5 {
        result.push_str(&format!(
            "    push {}\n    read_mem 1\n    pop 1\n",
            ADDRESS + i
        ));
    }
    result.push_str("    return\n");
    result
}
