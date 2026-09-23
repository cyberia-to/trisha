use trisha_honeycrisp::neptune_mine;
#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
use trisha_honeycrisp::neptune_mine::{PowMastPaths, HEIGHT};
#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
use trisha_honeycrisp::Digest;

fn main() {
    eprintln!("=== CPU benchmark (5s) ===");
    neptune_mine::benchmark_hardfork_beta(5.0);

    #[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
    {
        eprintln!("=== GPU benchmark (10s) ===");
        neptune_mine::benchmark_gpu(10.0);

        eprintln!("=== Unified CPU+GPU smoke test (10,000,000-attempt budget, zero target) ===");
        let path_a = [Digest::default(); HEIGHT];
        let mast = PowMastPaths::default();
        let target = Digest::default(); // zero target: only an all-zero digest wins
        let t0 = std::time::Instant::now();
        // Attempt budget, not a wall-clock deadline.
        let out = neptune_mine::mine_hardfork_beta_gpu(path_a, &mast, target, 10_000_000);
        let elapsed = t0.elapsed().as_secs_f64();
        eprintln!(
            "Unified smoke: {} in {:.2}s (expected None — target=0)",
            if out.is_some() {
                "found (unexpected!)"
            } else {
                "no winner"
            },
            elapsed
        );
    }

    #[cfg(not(all(feature = "gpu", target_os = "macos", target_arch = "aarch64")))]
    eprintln!("(GPU benchmark requires Apple Silicon macOS and --features gpu)");
}
