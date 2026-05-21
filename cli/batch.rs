use std::thread;

pub struct BatchResult<T> {
    pub index: usize,
    pub result: T,
    pub elapsed_ms: u64,
}

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
