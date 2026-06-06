//! [공격 1] YSC2 스트림 암호의 단일 키스트림 블록으로부터 내부 상태 완전 복구.
//!
//! 결정적 결함: `gen_ks_block`이 1024비트 순열의 출력 16개 워드 **전체**를
//! 키스트림으로 사출합니다(Salsa20/ChaCha20과 달리 feed-forward 없음).
//! 또한 순열은 가역적이므로, 128바이트의 키스트림이 곧 비밀 상태입니다.

#[path = "ysc2_ref.rs"]
mod ysc2_ref;
use ysc2_ref::{block_to_words, ysc2};

fn main() {
    // 임의의 키/논스로 정상 cipher를 구성.
    let key: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(31) ^ 0xA5);
    let nonce: [u8; 64] = std::array::from_fn(|i| (i as u8).wrapping_mul(17) ^ 0x5A);
    let rounds = 12;
    let secret_state = ysc2::init_state(&key, &nonce, rounds);

    // 정상 통신: 두 블록의 키스트림을 누출했다고 가정.
    // 알려진 평문 공격(KPA)이라면 평문 ⊕ 암호문이 곧 키스트림.
    let block1 = ysc2::gen_ks_block(&secret_state, 1, rounds);
    let block2 = ysc2::gen_ks_block(&secret_state, 2, rounds);

    println!("=== 공격 1: 1블록의 키스트림으로부터 YSC2 내부 상태 복구 ===\n");
    println!("실제 비밀 state[0..4]:");
    for i in 0..4 { println!("  state[{:2}] = {:016x}", i, secret_state[i]); }

    // --- 공격 ---
    // 1) 키스트림 한 블록을 순열의 출력 워드들로 파싱.
    let perm_out = block_to_words(&block1);
    // 2) 역순열을 통해 working_state(= state with state[0]^=counter) 복원.
    let mut working_state = perm_out;
    ysc2::inverse_permutation(&mut working_state, rounds);
    // 3) counter(=1) 제거하여 비밀 state 복원.
    let mut recovered = working_state;
    recovered[0] ^= 1;

    println!("\n복구한 state[0..4]:");
    for i in 0..4 { println!("  state[{:2}] = {:016x}", i, recovered[i]); }

    assert_eq!(recovered, secret_state, "상태 복구 실패");
    println!("\n[OK] 1024비트 비밀 상태 완전 복구 — 128바이트 KPA로 충분");

    // 4) 복구한 state로 두 번째 블록의 키스트림을 예측해 검증.
    let predicted_block2 = ysc2::gen_ks_block(&recovered, 2, rounds);
    assert_eq!(predicted_block2, block2);
    println!("[OK] 임의의 미래/과거 블록 예측 가능 (블록 2 일치 확인)");

    println!("\n작업량: 1024비트 순열 1회 역연산 = O(라운드 × 상태 크기) ≈ 12·16 워드 연산");
    println!("필요한 알려진 평문: 128바이트 (정확히 1블록)");
}
