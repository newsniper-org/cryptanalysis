//! 스레딩 추상화 (no_std 호환). `Spawner::join(f1, f2)`의 실행 방식은 구현체가 결정.
//!
//! - [`SerialSpawner`] — no_std 기본, 직렬 실행(실제 병렬 없음).
//! - [`StdThreadSpawner`] — `feature = "parallel"`(std 필요), active-thread 캡.
//!
//! no_std 멀티코어는 임베더가 [`Spawner`]를 직접 구현(이 trait엔 std 바운드 없음).

/// 두 작업을 join하는 추상화. 직렬/병렬 실행은 구현체 결정.
pub trait Spawner {
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send;
}

/// 직렬 spawner (no_std 기본).
#[derive(Clone, Copy, Debug, Default)]
pub struct SerialSpawner;

impl Spawner for SerialSpawner {
    #[inline]
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send,
    {
        (f1(), f2())
    }
}

/// `std::thread::scope` 기반 — active-thread 캡으로 thread 폭증 방지(`feature = "parallel"`).
#[cfg(feature = "parallel")]
#[derive(Debug)]
pub struct StdThreadSpawner {
    active: core::sync::atomic::AtomicUsize,
    max: usize,
}

#[cfg(feature = "parallel")]
impl StdThreadSpawner {
    /// `max` = `available_parallelism()`.
    pub fn new() -> Self {
        let max = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
        Self::with_max(max)
    }
    /// 동시 spawn thread 상한 명시(`max<=1`이면 사실상 직렬).
    pub fn with_max(max: usize) -> Self {
        Self { active: core::sync::atomic::AtomicUsize::new(0), max: max.max(1) }
    }
}

#[cfg(feature = "parallel")]
impl Default for StdThreadSpawner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "parallel")]
impl Spawner for StdThreadSpawner {
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send,
    {
        use core::sync::atomic::Ordering::Relaxed;
        let prev = self.active.fetch_add(1, Relaxed);
        if prev + 1 >= self.max {
            self.active.fetch_sub(1, Relaxed);
            (f1(), f2())
        } else {
            let r = std::thread::scope(|s| {
                let h1 = s.spawn(f1);
                let r2 = f2();
                (h1.join().unwrap(), r2)
            });
            self.active.fetch_sub(1, Relaxed);
            r
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serial_works() {
        assert_eq!(SerialSpawner.join(|| 1 + 1, || 2 + 2), (2, 4));
    }

    #[cfg(feature = "parallel")]
    #[test]
    fn std_thread_works() {
        assert_eq!(StdThreadSpawner::new().join(|| 1 + 1, || 2 + 2), (2, 4));
        assert_eq!(StdThreadSpawner::with_max(1).join(|| 10, || 20), (10, 20));
    }
}
