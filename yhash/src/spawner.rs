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
//! 참고: [`crate::parallel::hash_parallel`]는 leaf digest 수집에 `Vec`를 쓰므로
//! `alloc` feature가 필요하다 (no_std + alloc). 스트리밍 `update`/`finalize`는
//! `alloc` 없이도 동작하지만 직렬이다.

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

/// `std::thread::scope` 사용. *현재 thread에서 f2를 실행*하고 *새 thread에서 f1을 spawn*.
#[cfg(feature = "std-thread")]
#[derive(Clone, Copy, Debug, Default)]
pub struct StdThreadSpawner;

#[cfg(feature = "std-thread")]
impl Spawner for StdThreadSpawner {
    fn join<F1, F2, R1, R2>(&self, f1: F1, f2: F2) -> (R1, R2)
    where
        F1: FnOnce() -> R1 + Send,
        F2: FnOnce() -> R2 + Send,
        R1: Send,
        R2: Send,
    {
        std::thread::scope(|s| {
            let h1 = s.spawn(f1);
            let r2 = f2();
            let r1 = h1.join().unwrap();
            (r1, r2)
        })
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
        let s = StdThreadSpawner;
        let (a, b) = s.join(|| 1 + 1, || 2 + 2);
        assert_eq!((a, b), (2, 4));
    }

    #[cfg(feature = "rayon")]
    #[test]
    fn rayon_spawner_works() {
        let s = RayonSpawner;
        let (a, b) = s.join(|| 1 + 1, || 2 + 2);
        assert_eq!((a, b), (2, 4));
    }
}
