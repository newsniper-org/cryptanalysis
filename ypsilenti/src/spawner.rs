//! Threading abstraction. `no_std` compatible.
//!
//! `Spawner::join(f1, f2)` 가 두 closure를 *어떻게* 실행할지는 구현체가 결정.
//! 기본 `SerialSpawner`는 직렬 실행 (no_std OK).
//! `std-thread` 또는 `rayon` feature로 진정한 병렬 실행을 가능하게 함.
//!
//! # no_std 환경에서의 병렬 실행
//!
//! **순수 no_std(core/alloc)에는 이식 가능한 스레드 생성 수단이 없다.** 스레드를
//! 띄우려면 OS(=std) 또는 플랫폼별 실행기가 필요하다. 따라서:
//!
//! - [`SerialSpawner`] — no_std 기본. *직렬* 실행 (실제 병렬성 없음).
//! - [`StdThreadSpawner`] / [`RayonSpawner`] — `std`가 *필수* (feature-gated).
//!
//! 그러면 no_std에서 진짜 MT는? → **임베더가 [`Spawner`]를 직접 구현**한다.
//! 이 trait 자체에는 `std` 바운드가 없으므로, 멀티코어 RTOS·베어메탈 실행기
//! (embassy, RTIC), FreeRTOS task FFI 등 *플랫폼이 제공하는* 동시성 위에 얹으면 된다.
//! 즉 라이브러리는 *추상화*만 no_std로 제공하고, *어떻게 병렬화할지*는 그 플랫폼의
//! 동시성 프리미티브를 아는 임베더의 몫이다.
//!
//! ```ignore
//! // no_std 멀티코어 플랫폼 예시 (개념)
//! struct MyRtosSpawner;
//! impl Spawner for MyRtosSpawner {
//!     fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
//!     where F1: FnOnce() -> R1 + Send, F2: FnOnce() -> R2 + Send, R1: Send, R2: Send {
//!         // 플랫폼의 코어-핀 task로 f1을 띄우고, 현재 core에서 f2 실행 후 join.
//!         // (scoped 비-'static closure 처리에 unsafe가 필요할 수 있으나, 그건
//!         //  임베더 crate에서. 이 crate는 forbid(unsafe_code).)
//!         todo!()
//!     }
//! }
//! ```

/// 두 작업을 join하는 추상화.
///
/// `(F1, F2) -> (R1, R2)` 의 *어떻게 실행할지*는 구현체가 결정.
pub trait Spawner {
    /// 두 작업을 join. 직렬 또는 병렬 실행은 구현체가 결정.
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send;
}

/// 직렬 실행 spawner. `no_std` 기본 채택.
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
        let r1 = f1();
        let r2 = f2();
        (r1, r2)
    }
}

// ---- std::thread::scope 기반 (feature gated) ----

/// `std::thread::scope` 기반 spawner — **active-thread 캡**으로 thread 폭증 방지.
///
/// 단순히 `join`마다 새 thread를 spawn하면 divide-and-conquer가 O(leaves)개의
/// thread를 만들어 leaf가 작을 때 오히려 직렬보다 느려진다 (벤치에서 확인됨).
/// 이 구현은 *동시에 spawn된 thread 수*를 [`AtomicUsize`]로 추적해 `max`에
/// 도달하면 해당 `join`은 *직렬* 실행한다 (= 깊은 재귀는 thread를 더 만들지 않음).
///
/// `max`는 기본적으로 `available_parallelism()`. work-stealing 풀이 필요하면
/// [`RayonSpawner`]가 보통 더 낫다 — 이건 rayon 의존성 없는 환경의 선택지.
#[cfg(feature = "std-thread")]
#[derive(Debug)]
pub struct StdThreadSpawner {
    active: core::sync::atomic::AtomicUsize,
    max: usize,
}

#[cfg(feature = "std-thread")]
impl StdThreadSpawner {
    /// `max` = `available_parallelism()` 로 새 spawner.
    pub fn new() -> Self {
        let max = std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1);
        Self::with_max(max)
    }

    /// 동시 spawn thread 상한을 명시. `max <= 1` 이면 사실상 직렬.
    pub fn with_max(max: usize) -> Self {
        Self {
            active: core::sync::atomic::AtomicUsize::new(0),
            max: max.max(1),
        }
    }
}

#[cfg(feature = "std-thread")]
impl Default for StdThreadSpawner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "std-thread")]
impl Spawner for StdThreadSpawner {
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send,
    {
        use core::sync::atomic::Ordering::Relaxed;
        // 현재 active thread 수가 max 미만일 때만 새 thread를 spawn.
        let prev = self.active.fetch_add(1, Relaxed);
        if prev + 1 >= self.max {
            // 캡 도달 — 직렬 실행 (이 경로는 thread를 만들지 않음).
            self.active.fetch_sub(1, Relaxed);
            let r1 = f1();
            let r2 = f2();
            (r1, r2)
        } else {
            let r = std::thread::scope(|s| {
                let h1 = s.spawn(f1);
                let r2 = f2();
                let r1 = h1.join().unwrap();
                (r1, r2)
            });
            self.active.fetch_sub(1, Relaxed);
            r
        }
    }
}

// ---- rayon::join 기반 (feature gated) ----

/// `rayon::join` 사용 — global thread pool 활용.
#[cfg(feature = "rayon")]
#[derive(Clone, Copy, Debug, Default)]
pub struct RayonSpawner;

#[cfg(feature = "rayon")]
impl Spawner for RayonSpawner {
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send,
    {
        rayon::join(f1, f2)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serial_spawner_works() {
        let s = SerialSpawner;
        let (a, b) = s.join(|| 1 + 1, || 2 + 2);
        assert_eq!((a, b), (2, 4));
    }

    #[cfg(feature = "std-thread")]
    #[test]
    fn std_thread_spawner_works() {
        let s = StdThreadSpawner::new();
        let (a, b) = s.join(|| 1 + 1, || 2 + 2);
        assert_eq!((a, b), (2, 4));
    }

    #[cfg(feature = "std-thread")]
    #[test]
    fn std_thread_spawner_capped_serial() {
        let s = StdThreadSpawner::with_max(1);
        let (a, b) = s.join(|| 10, || 20);
        assert_eq!((a, b), (10, 20));
    }

    #[cfg(feature = "rayon")]
    #[test]
    fn rayon_spawner_works() {
        let s = RayonSpawner;
        let (a, b) = s.join(|| 1 + 1, || 2 + 2);
        assert_eq!((a, b), (2, 4));
    }
}
