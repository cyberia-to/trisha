//! Host-only bounded reservations and write-once publication.
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Mutex,
};
pub(crate) struct Attempts {
    next: AtomicU64,
    end: u64,
}
impl Attempts {
    pub(crate) fn new(start: u64, count: u64) -> Self {
        Self {
            next: AtomicU64::new(start),
            end: start.checked_add(count).expect("attempt range overflow"),
        }
    }
    pub(crate) fn reserve(&self, count: u64) -> Option<std::ops::Range<u64>> {
        if count == 0 {
            return None;
        }
        let start = self
            .next
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |n| {
                (n < self.end).then(|| n.saturating_add(count).min(self.end))
            })
            .ok()?;
        Some(start..start.saturating_add(count).min(self.end))
    }
}
pub(crate) struct Winner<T>(Mutex<Option<T>>);
impl<T> Winner<T> {
    pub(crate) fn new() -> Self {
        Self(Mutex::new(None))
    }
    pub(crate) fn found(&self) -> bool {
        self.0.lock().unwrap().is_some()
    }
    pub(crate) fn publish(&self, value: T) {
        self.0.lock().unwrap().get_or_insert(value);
    }
    pub(crate) fn take(self) -> Option<T> {
        self.0.into_inner().unwrap()
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reservations_cover_exact_limits_without_overflow() {
        for limit in [0, 1, 255, 256, 257, 1025] {
            let attempts = Attempts::new(u64::MAX - limit, limit);
            let ranges = Mutex::new(Vec::new());
            std::thread::scope(|s| {
                for size in [1, 256, 3] {
                    let a = &attempts;
                    let r = &ranges;
                    s.spawn(move || {
                        while let Some(range) = a.reserve(size) {
                            r.lock().unwrap().push(range);
                        }
                    });
                }
            });
            let mut ranges = ranges.into_inner().unwrap();
            ranges.sort_by_key(|r| r.start);
            let mut cursor = u64::MAX - limit;
            for range in ranges {
                assert_eq!(range.start, cursor);
                assert!(range.end > range.start);
                cursor = range.end;
            }
            assert_eq!(cursor, u64::MAX);
        }
    }
    #[test]
    fn cpu_winner_survives_completed_gpu_dispatch() {
        let winner = Winner::new();
        let barrier = std::sync::Barrier::new(2);
        std::thread::scope(|s| {
            s.spawn(|| {
                winner.publish("cpu");
                barrier.wait();
            });
            barrier.wait(); // deterministic CPU win while simulated dispatch was in flight
            winner.publish("gpu");
        });
        assert_eq!(winner.take(), Some("cpu"));
        let winner = Winner::new();
        winner.publish("gpu");
        winner.publish("cpu");
        assert_eq!(winner.take(), Some("gpu"));
    }
}
