#!/usr/bin/env python3
"""
Amaryllises+ARX 재설계 비교실험 (ypsilenti 스케일 8×u32).

공통 설계(모든 변형 공통):
  (1) F 회전 수정, (2) ARX 결합기 y_i = ROTR_b(ROTL_a(x_i) ⊞ t),
  (3) Amaryllises류: 레인별 *비선형* 결합 (σ-GLM의 선형 XOR-broadcast 아님).
σ-GLM(XOR-broadcast)은 *대조 baseline* 으로만 포함.

축1: F 3-term vs 4-term.   축2: σ(distinct-μ) 레인 {0,4} vs {0,2,4,6}.   라운드 sweep.

측정: 경험적 best 단일특성 DP = max_δ max_{Δ} Pr[δ→Δ] (np.unique로 정확).
      prob-1(=DP 1.0) 잔존 여부 = 확률-1 (선형) 차분 검출.
      weight = -log2(DP).  ARX는 GF(2)-비선형 → R* 선형대수 대신 이 경험측정 사용.
"""
import numpy as np

MASK = np.uint64(0xFFFFFFFF)
RED  = np.uint64(0x400007)          # GF(2^32) reduction (σ의 α-곱)
P_PI = [7, 4, 1, 6, 3, 0, 5, 2]
ARX_L, ARX_R = 8, 3                 # rotate-add-rotate 회전량

def rotl(x, k):
    k %= 32
    if k == 0: return x & MASK
    return ((x << np.uint64(k)) | (x >> np.uint64(32 - k))) & MASK
def rotr(x, k): return rotl(x, (32 - k) % 32)

def alpha(y):                       # α-곱 (branchless)
    top = (y >> np.uint64(31)) & np.uint64(1)
    return ((y << np.uint64(1)) & MASK) ^ (top * RED)
def alpha_pow(y, k):
    for _ in range(k): y = alpha(y)
    return y

def Ffun(s, terms):
    out = s.copy()
    for (a, b) in terms:
        out ^= rotl(s, a) & rotl(s, b)
    return out & MASK

def permute(state, rounds, combiner, terms, sigma):
    # state: (8, N) uint64
    st = [state[i].copy() for i in range(8)]
    for _ in range(rounds):
        S = st[0].copy()
        for i in range(1, 8): S = S ^ st[i]
        t = Ffun(S, terms)
        if combiner == 'xor':
            new = [st[i] ^ t for i in range(8)]
        else:  # arx: ROTR_R(ROTL_L(x) + t)
            new = [rotr((rotl(st[i], ARX_L) + t) & MASK, ARX_R) for i in range(8)]
        for (lane, k) in sigma:
            new[lane] = alpha_pow(new[lane], k)
        st = [new[P_PI[i]] for i in range(8)]
    return np.stack(st)

def delta_set():
    ds = []
    # active 단일비트 (word0)
    for j in (0, 8, 16, 24):
        d = np.zeros(8, dtype=np.uint64); d[0] = np.uint64(1 << j); ds.append(d)
    # inactive 쌍 (word0=word1 → ⊕S=0; σ-GLM의 prob-1 운반자)
    for j in (0, 8, 16, 24):
        d = np.zeros(8, dtype=np.uint64); d[0] = d[1] = np.uint64(1 << j); ds.append(d)
    return ds

def best_dp(rounds, combiner, terms, sigma, N=20000, seed=0):
    rng = np.random.default_rng(seed)
    base = (rng.integers(0, 1 << 32, size=(8, N), dtype=np.uint64))
    best, prob1 = 0.0, False
    for d in delta_set():
        xd = base ^ d[:, None]
        y  = permute(base, rounds, combiner, terms, sigma)
        yd = permute(xd,   rounds, combiner, terms, sigma)
        diff = (y ^ yd)
        _, counts = np.unique(diff.T, axis=0, return_counts=True)
        c = counts.max()
        dp = c / N
        if dp > best: best = dp
        if c == N: prob1 = True
    return best, prob1

F3 = [(7, 17), (3, 21), (9, 29)]
F4 = F3 + [(5, 27)]
F2_orig = [(7, 17), (3, 13)]        # 원래 ypsilenti (R2 결함)

CONFIGS = [
    ("[baseline] σ-GLM XOR, 2-term(원본), σ{0,4}", 'xor', F2_orig, [(0,1),(4,3)]),
    ("Amaryllises+ARX, 3-term, σ{0,4}",            'arx', F3, [(0,1),(4,3)]),
    ("Amaryllises+ARX, 4-term, σ{0,4}",            'arx', F4, [(0,1),(4,3)]),
    ("Amaryllises+ARX, 3-term, σ{0,2,4,6}",        'arx', F3, [(0,1),(2,5),(4,3),(6,7)]),
    ("Amaryllises+ARX, 4-term, σ{0,2,4,6}",        'arx', F4, [(0,1),(2,5),(4,3),(6,7)]),
]
ROUNDS = [2, 4, 6, 8, 10, 12]

def w(dp): return "prob-1" if dp >= 1.0 else f"2^-{-np.log2(dp):.1f}" if dp > 0 else ">2^-14"

print("경험적 best 단일특성 DP (낮을수록 강함); 'prob-1' = 확률-1 차분 잔존\n")
print(f"{'config':<42}" + "".join(f" R={r:<7}" for r in ROUNDS))
for name, comb, terms, sig in CONFIGS:
    row = f"{name:<42}"
    for r in ROUNDS:
        dp, p1 = best_dp(r, comb, terms, sig)
        row += f" {w(dp):<8}"
    print(row)
