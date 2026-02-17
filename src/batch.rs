//! Generic parallel executor for batch operations.
//!
//! Any operation (run, prove, verify, deploy) can use `run_batch` to
//! execute jobs in parallel with bounded concurrency.

use std::thread;

/// Result of a single batch job.
pub struct BatchResult<T> {
    /// Zero-based index of this job in the input list.
    pub index: usize,
    /// The result produced by the job closure.
    pub result: T,
    /// Wall-clock time in milliseconds.
    pub elapsed_ms: u64,
}

/// Execute `jobs` in parallel, applying `f` to each.
///
/// At most `max_parallel` jobs run concurrently. Results are returned
/// in the same order as the input jobs.
pub fn run_batch<J, T, F>(jobs: Vec<J>, max_parallel: usize, f: F) -> Vec<BatchResult<T>>
where
    J: Send,
    T: Send,
    F: Fn(J) -> T + Send + Sync,
{
    let max_parallel = max_parallel.max(1);

    thread::scope(|scope| {
        let f = &f;
        let mut results: Vec<Option<BatchResult<T>>> = (0..jobs.len()).map(|_| None).collect();
        let mut handles: Vec<(usize, thread::ScopedJoinHandle<'_, (T, u64)>)> = Vec::new();

        for (index, job) in jobs.into_iter().enumerate() {
            // Drain finished handles when at capacity
            if handles.len() >= max_parallel {
                let (idx, handle) = handles.remove(0);
                let (result, elapsed_ms) = handle.join().expect("batch job panicked");
                results[idx] = Some(BatchResult {
                    index: idx,
                    result,
                    elapsed_ms,
                });
            }

            let handle = scope.spawn(move || {
                let start = std::time::Instant::now();
                let result = f(job);
                let elapsed_ms = start.elapsed().as_millis() as u64;
                (result, elapsed_ms)
            });
            handles.push((index, handle));
        }

        // Drain remaining handles
        for (idx, handle) in handles {
            let (result, elapsed_ms) = handle.join().expect("batch job panicked");
            results[idx] = Some(BatchResult {
                index: idx,
                result,
                elapsed_ms,
            });
        }

        results
            .into_iter()
            .map(|r| r.expect("missing result"))
            .collect()
    })
}
