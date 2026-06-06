//! YSC2 / AuxCrypt 사양에 따른 순열 및 역순열 표준 구현.
//! 라이브러리 소스코드(`ysc2/src/backends/soft.rs`, `auxcrypt/src/backends/soft.rs`,
//! `ysc2/src/stream.rs`, `auxcrypt/src/stream.rs`)를 그대로 옮긴 것이며,
//! 키스트림 생성/초기화 로직까지 모두 재현합니다.

pub const STATE_WORDS: usize = 16;

// --- YSC2 상수 (ysc2/src/consts.rs) ---
pub mod ysc2 {
    pub const ROT_A: u32 = 13;
    pub const ROT_B: u32 = 37;
    pub const RC: [u64; 16] = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    ];
    pub const P: [usize; 16] = [
        0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11,
    ];

    #[inline(always)]
    pub fn g(x: u64) -> u64 {
        x ^ (x.rotate_left(ROT_A) & x.rotate_left(ROT_B))
    }

    /// 정방향 순열 (라이브러리와 비트 단위로 동일).
    pub fn permutation(state: &mut [u64; 16], rounds: usize) {
        for r in 0..rounds {
            state[0] ^= RC[r];
            let mut temp = [0u64; 8];
            for i in 0..8 {
                temp[i] = g(state[i]);
            }
            for i in 0..8 {
                state[i + 8] ^= temp[i];
            }
            for i in 0..8 {
                state[i] ^= state[i + 8];
            }
            let mut new_state = [0u64; 16];
            for i in 0..16 {
                new_state[i] = state[P[i]];
            }
            *state = new_state;
        }
    }

    /// 역순열. 각 라운드를 역순으로 풀어 입력을 복원한다.
    ///
    /// 라운드의 세 단계는 모두 가역적:
    ///   - AddRoundConstant: state[0] ^= RC[r]  (자기 자신이 역)
    ///   - Lai-Massey-유사: (L, R) → (L', R') = (L ⊕ R ⊕ g(L), R ⊕ g(L))
    ///       역연산: L = L' ⊕ R', R = R' ⊕ g(L)
    ///   - 워드 순열: new[i] = state[P[i]]
    ///       역: state[P[i]] = new[i]
    pub fn inverse_permutation(state: &mut [u64; 16], rounds: usize) {
        for r in (0..rounds).rev() {
            // 1) 워드 순열 역적용: prev[P[i]] = state[i]
            let mut prev = [0u64; 16];
            for i in 0..16 {
                prev[P[i]] = state[i];
            }
            *state = prev;

            // 2) Lai-Massey 역연산
            // L' = L ⊕ R ⊕ g(L), R' = R ⊕ g(L)
            // L = L' ⊕ R'  (왜냐하면 L' ⊕ R' = L)
            for i in 0..8 {
                state[i] ^= state[i + 8];      // L = L' ⊕ R' (역으로 풀기)
            }
            for i in 0..8 {
                let gl = g(state[i]);
                state[i + 8] ^= gl;             // R = R' ⊕ g(L)
            }

            // 3) 라운드 상수 역적용
            state[0] ^= RC[r];
        }
    }

    /// `Ysc2_512StreamCipher` 초기화. (key_size_bytes = 64 또는 128)
    pub fn init_state(key: &[u8], iv: &[u8], rounds: usize) -> [u64; 16] {
        let mut state = [0u64; 16];
        if key.len() == 128 {
            for (i, chunk) in key.chunks_exact(8).enumerate() {
                state[i] = u64::from_le_bytes(chunk.try_into().unwrap());
            }
            for (i, chunk) in iv.chunks_exact(8).enumerate() {
                state[i + 8] ^= u64::from_le_bytes(chunk.try_into().unwrap());
            }
        } else {
            for (i, chunk) in key.chunks_exact(8).enumerate() {
                state[i] = u64::from_le_bytes(chunk.try_into().unwrap());
            }
            for (i, chunk) in iv.chunks_exact(8).enumerate() {
                state[i + 8] = u64::from_le_bytes(chunk.try_into().unwrap());
            }
        }
        permutation(&mut state, rounds);
        state
    }

    /// 한 블록(1024비트) 분량의 키스트림을 생성. 라이브러리의 `gen_ks_block`과 동일.
    pub fn gen_ks_block(state: &[u64; 16], counter: u64, rounds: usize) -> [u8; 128] {
        let mut working = *state;
        working[0] ^= counter;
        permutation(&mut working, rounds);
        let mut out = [0u8; 128];
        for i in 0..16 {
            out[i * 8..(i + 1) * 8].copy_from_slice(&working[i].to_le_bytes());
        }
        out
    }
}

// --- AuxCrypt 상수 (auxcrypt/src/consts.rs) ---
pub mod auxcrypt {
    pub const ROT_A: u32 = 19;
    pub const ROT_B: u32 = 41;
    pub const RC: [u64; 20] = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    ];
    pub const P: [usize; 16] = [
        0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11,
    ];

    /// 비선형(?)이라고 명명된 함수. 실제로는 affine: f(x) = ¬x ⊕ rot_a(x) ⊕ rot_b(x)
    #[inline(always)]
    pub fn f(x: u64) -> u64 {
        (!x) ^ x.rotate_left(ROT_A) ^ x.rotate_left(ROT_B)
    }

    #[inline(always)]
    fn lai_massey_round(state: &mut [u64; 16], a: usize, b: usize) {
        let diff = f(state[a] ^ state[b]);
        state[a] ^= diff;
        state[b] ^= diff;
    }

    pub fn permutation(state: &mut [u64; 16], rounds: usize) {
        for r in 0..rounds {
            state[0] ^= RC[r];
            for i in 0..8 { lai_massey_round(state, 2 * i, 2 * i + 1); }
            for i in 0..4 {
                lai_massey_round(state, 4 * i, 4 * i + 2);
                lai_massey_round(state, 4 * i + 1, 4 * i + 3);
            }
            for i in 0..2 {
                for j in 0..4 { lai_massey_round(state, 8 * i + j, 8 * i + j + 4); }
            }
            for i in 0..8 { lai_massey_round(state, i, i + 8); }

            let mut new_state = [0u64; 16];
            for i in 0..16 {
                new_state[i] = state[P[i]];
            }
            *state = new_state;
        }
    }

    /// 단일 Lai-Massey 라운드의 역연산. diff = f(a ⊕ b)이고
    /// (a ⊕ diff) ⊕ (b ⊕ diff) = a ⊕ b → diff는 a', b'로부터 동일하게 계산됨.
    #[inline(always)]
    fn lai_massey_round_inv(state: &mut [u64; 16], a: usize, b: usize) {
        let diff = f(state[a] ^ state[b]);
        state[a] ^= diff;
        state[b] ^= diff;
    }

    pub fn inverse_permutation(state: &mut [u64; 16], rounds: usize) {
        for r in (0..rounds).rev() {
            // 1) 워드 순열 역
            let mut prev = [0u64; 16];
            for i in 0..16 {
                prev[P[i]] = state[i];
            }
            *state = prev;

            // 2) Lai-Massey 라운드들을 역순으로
            for i in 0..8 { lai_massey_round_inv(state, i, i + 8); }
            for i in 0..2 {
                for j in 0..4 { lai_massey_round_inv(state, 8 * i + j, 8 * i + j + 4); }
            }
            for i in 0..4 {
                lai_massey_round_inv(state, 4 * i, 4 * i + 2);
                lai_massey_round_inv(state, 4 * i + 1, 4 * i + 3);
            }
            for i in 0..8 { lai_massey_round_inv(state, 2 * i, 2 * i + 1); }

            // 3) RC 역적용
            state[0] ^= RC[r];
        }
    }

    pub fn init_state(key: &[u8], iv: &[u8], rounds: usize) -> [u64; 16] {
        let mut state = [0u64; 16];
        for (i, chunk) in key.chunks_exact(8).enumerate() {
            state[i] = u64::from_le_bytes(chunk.try_into().unwrap());
        }
        for (i, chunk) in iv.chunks_exact(8).enumerate() {
            state[8 + i] ^= u64::from_le_bytes(chunk.try_into().unwrap());
        }
        permutation(&mut state, rounds);
        state
    }

    pub fn gen_ks_block(state: &[u64; 16], counter: u64, rounds: usize) -> [u8; 128] {
        let mut working = *state;
        working[0] ^= counter;
        permutation(&mut working, rounds);
        let mut out = [0u8; 128];
        for i in 0..16 {
            out[i * 8..(i + 1) * 8].copy_from_slice(&working[i].to_le_bytes());
        }
        out
    }
}

/// 키스트림 16바이트 워드 ↔ u64 LE 단어 16개 변환.
pub fn block_to_words(blk: &[u8; 128]) -> [u64; 16] {
    let mut out = [0u64; 16];
    for i in 0..16 {
        out[i] = u64::from_le_bytes(blk[i * 8..(i + 1) * 8].try_into().unwrap());
    }
    out
}
