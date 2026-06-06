//! YHash 순열 wrapper. YSC4-p를 reduced-round로 사용.

use crate::consts::{rounds, STATE_BYTES, STATE_WORDS};

/// YHash 상태 = YSC4-p 상태.
pub type State = [u64; STATE_WORDS];

/// 16-byte mask seed를 128-byte block으로 패딩 후 IV와 XOR해 mask 도출 입력 생성.
#[inline]
fn pad_mask_seed_into_state(seed: &[u8; 16], iv: &State) -> State {
    let mut s = *iv;
    // seed (16 byte)를 state의 처음 2 워드에 LE u64로 적재 후 XOR.
    let w0 = u64::from_le_bytes(seed[0..8].try_into().unwrap());
    let w1 = u64::from_le_bytes(seed[8..16].try_into().unwrap());
    s[0] ^= w0;
    s[1] ^= w1;
    s
}

/// mask seed로부터 1024-bit mask 도출.
/// `mask = P(IV ⊕ pad(seed))` (R = rounds::MASK_DERIVE).
#[inline]
pub fn derive_mask(seed: &[u8; 16], iv: &State) -> State {
    let mut s = pad_mask_seed_into_state(seed, iv);
    ysc4::permutation::permute(&mut s, rounds::MASK_DERIVE);
    s
}

/// 블록을 mask와 XOR 후 압축 라운드 적용 → leaf/internal block contribution.
#[inline]
pub fn compress_block(block: &[u8; STATE_BYTES], mask: &State, rounds: usize) -> State {
    let mut s = [0u64; STATE_WORDS];
    for i in 0..STATE_WORDS {
        let w = u64::from_le_bytes(block[i * 8..(i + 1) * 8].try_into().unwrap());
        s[i] = w ^ mask[i];
    }
    ysc4::permutation::permute(&mut s, rounds);
    s
}

/// Finalize: state ⊕ mask_mid → P(R = FINALIZE).
#[inline]
pub fn finalize(state: &State, mask_mid: &State) -> State {
    let mut s = *state;
    for i in 0..STATE_WORDS {
        s[i] ^= mask_mid[i];
    }
    ysc4::permutation::permute(&mut s, rounds::FINALIZE);
    s
}

/// State의 첫 32 byte (= 256-bit chaining value)를 추출.
#[inline]
pub fn truncate_cv(state: &State) -> [u8; 32] {
    let mut cv = [0u8; 32];
    cv[0..8].copy_from_slice(&state[0].to_le_bytes());
    cv[8..16].copy_from_slice(&state[1].to_le_bytes());
    cv[16..24].copy_from_slice(&state[2].to_le_bytes());
    cv[24..32].copy_from_slice(&state[3].to_le_bytes());
    cv
}

/// CV bytes (32 byte) → state (state[0..4]는 CV, 나머지는 0).
#[inline]
pub fn cv_to_state(cv: &[u8; 32]) -> State {
    let mut s = [0u64; STATE_WORDS];
    s[0] = u64::from_le_bytes(cv[0..8].try_into().unwrap());
    s[1] = u64::from_le_bytes(cv[8..16].try_into().unwrap());
    s[2] = u64::from_le_bytes(cv[16..24].try_into().unwrap());
    s[3] = u64::from_le_bytes(cv[24..32].try_into().unwrap());
    s
}
