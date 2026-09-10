use trisha_honeycrisp::neptune_mine;
#[cfg(feature = "gpu")]
use trisha_honeycrisp::neptune_mine::{PowMastPaths, HEIGHT};
#[cfg(feature = "gpu")]
use trisha_honeycrisp::Digest;

fn main() {
    eprintln!("=== CPU benchmark (5s) ===");
    neptune_mine::benchmark_hardfork_beta(5.0);

    #[cfg(feature = "gpu")]
    {
        eprintln!("=== GPU benchmark (10s) ===");
        neptune_mine::benchmark_gpu(10.0);

        eprintln!("=== Unified CPU+GPU smoke test (10s budget, unreachable target) ===");
        let path_a = [Digest::default(); HEIGHT];
        let mast = PowMastPaths::default();
        let target = Digest::default(); // all-zeros — nothing wins
        let t0 = std::time::Instant::now();
        // ~10M attempts — at ~1.5 MH/s combined that's ~6.5s; budget 10M attempts.
        let out = neptune_mine::mine_hardfork_beta_gpu(path_a, &mast, target, 10_000_000);
        let elapsed = t0.elapsed().as_secs_f64();
        eprintln!(
            "Unified smoke: {} in {:.2}s (expected None — target=0)",
            if out.is_some() { "found (unexpected!)" } else { "no winner" },
            elapsed
        );
    }

    #[cfg(not(feature = "gpu"))]
    eprintln!("(build with --features gpu to enable GPU benchmark)");
}
