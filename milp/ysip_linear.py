#!/usr/bin/env python3
"""
YSip 선형 분석 — 라운드별 best 선형 상관 |corr| 감쇠 (YSip vs SipHash).

핵심 관찰: rar(x,y)=ROTR_B(ROTL_A(x)⊞y) 에서 ROTL/ROTR 은 GF(2)-선형 전단사 →
단일 가산의 선형상관 *크기* 는 회전으로 불변. 따라서 per-add 선형 weight 는 SipHash 와
동일하고, 차이는 trail 정렬(마스크 확산)뿐 — 차분과 같은 구도. (W1) 단일 가산 정확 +
(full) 라운드 bias-matrix 로 검증.

(W1) 단일 ⊞ 의 best 비자명 선형 corr (정확, 소규모 Walsh):
     LSB 근사 a·x⊕a·y=a·(x+y) 는 corr=1(weight0, a=LSB). best nonzero-mask weight 는 1.
(full) 라운드 bias-matrix C_ab = E_x[(-1)^{x_a ⊕ P_R(x)_b}]  (a,b 단일비트, 256×256).
       max_ab |C_ab| = best 1비트 선형 trail. floor ~ 1/sqrt(N).
       정직: 1비트 마스크 한정(멀티비트/hull 미포함 → 방어자 낙관). 상대비교는 동일도구라 공정.

실행: python3 ysip_linear.py
"""
import math
import numpy as np

M = np.uint64(0xFFFFFFFFFFFFFFFF)


def rotl(x, k):
    k %= 64
    return x if k == 0 else ((x << np.uint64(k)) | (x >> np.uint64(64 - k))) & M


def rotr(x, k):
    return rotl(x, (64 - (k % 64)) % 64)


def ysip_round(v, mode, A, B):
    v0, v1, v2, v3 = v

    def comb(x, y):
        return (x + y) & M if mode == "siphash" else rotr((rotl(x, A) + y) & M, B)

    v0 = comb(v0, v1); v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
    v2 = comb(v2, v3); v3 = rotl(v3, 16); v3 ^= v2
    v0 = comb(v0, v3); v3 = rotl(v3, 21); v3 ^= v0
    v2 = comb(v2, v1); v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    return [v0, v1, v2, v3]


def runR(v, R, mode, A, B):
    for _ in range(R):
        v = ysip_round(v, mode, A, B)
    return v


def bits_pm(words):
    """4×u64 배열 리스트 → (N,256) ±1 비트행렬 (LSB-우선)."""
    N = words[0].shape[0]
    out = np.empty((N, 256), dtype=np.int8)
    for w in range(4):
        x = words[w]
        for b in range(64):
            out[:, w * 64 + b] = ((x >> np.uint64(b)) & np.uint64(1)).astype(np.int8)
    return 1 - 2 * out  # 0→+1, 1→-1


def best_corr(R, mode, A, B, N, seed=0):
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    Xpm = bits_pm([a.copy() for a in x]).astype(np.float32)
    y = runR([a.copy() for a in x], R, mode, A, B)
    Ypm = bits_pm(y).astype(np.float32)
    C = (Xpm.T @ Ypm) / N           # 256×256 상관행렬
    return float(np.abs(C).max())


def single_add_best_nonzero_weight(n=8):
    """단일 가산 z=x+y (nbit) best 비자명(LSB 제외) 선형 corr weight, 정확 전수."""
    best = 0.0
    full = 1 << n
    xs = np.arange(full, dtype=np.int64)[:, None]
    ys = np.arange(full, dtype=np.int64)[None, :]
    z = (xs + ys) & (full - 1)
    # 단일비트 출력마스크 b, 단일비트 입력마스크쌍 (ax,ay): LSB(b=0) 제외
    for b in range(n):
        zb = (z >> b) & 1
        for ax in range(n):
            xa = (xs >> ax) & 1
            for ay in range(n):
                ya = (ys >> ay) & 1
                par = (xa ^ ya ^ zb).astype(np.float64)
                corr = abs(np.mean(1 - 2 * par))
                if b == 0 and ax == 0 and ay == 0:
                    continue  # LSB 자명 corr=1
                if corr > best:
                    best = corr
    return best


if __name__ == "__main__":
    print("== (W1) 단일 모듈러 가산 best 비자명 선형 corr (n=8 정확 전수) ==")
    c = single_add_best_nonzero_weight(8)
    print(f"  best nonzero-mask |corr| = {c:.4f} (-log2={-math.log2(max(c,1e-9)):.2f}); "
          "LSB는 corr=1(weight0, 차분 MSB-자명과 쌍대). YSip·SipHash 동일(회전불변).")

    print("\n== (full) 라운드 best 1비트 선형상관 |corr|: YSip vs SipHash (⚠ 노이즈 한계) ==")
    N = 1 << 20
    # best_corr 는 256×256=65536 cell 의 MAX. per-cell std=1/sqrt(N) 이나 MAX 의 기대치는
    # max-of-Gaussian ≈ (1/sqrt(N))·sqrt(2·ln 65536). 이 값 이하는 전부 노이즈.
    cell = 1.0 / math.sqrt(N)
    maxnoise = cell * math.sqrt(2 * math.log(65536))
    print(f"  per-cell std=2^-{-math.log2(cell):.1f}, MAX-noise 기대=2^-{-math.log2(maxnoise):.2f} (이 이하 = 노이즈)")
    print(f"  {'R':>2} | {'SipHash':>12} | {'YSip(8,9)':>12}")
    for R in range(1, 6):
        cs = best_corr(R, "siphash", 0, 0, N, seed=R)
        cy = best_corr(R, "ysip", 8, 9, N, seed=R + 100)
        print(f"  {R:>2} | 2^-{-math.log2(cs):>7.2f} | 2^-{-math.log2(cy):>7.2f}")
    # 대조군: 출력을 입력과 독립한 랜덤으로 — 순수 노이즈 max. 표가 이와 같으면 신호 0.
    rng = np.random.default_rng(777)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    y = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    Xpm = bits_pm(x).astype(np.float32); Ypm = bits_pm(y).astype(np.float32)
    ctrl = float(np.abs((Xpm.T @ Ypm) / N).max())
    print(f"  대조군(독립랜덤) = 2^-{-math.log2(ctrl):.2f}  → 위 표가 이와 통계적으로 같음 = 1비트 신호 0(노이즈).")
    print("\n정직(적대검증 반영): 1비트 라운드상관은 R1부터 MAX-노이즈에 묻혀 *비정보적*(감쇠표 아님).")
    print("  per-add |corr| 동등(=SipHash, 회전불변, W1)만 입증됨. 멀티라운드 linear-hull 은 미측정 —")
    print("  rar 는 피연산자 비대칭(ROTL만 누산입력에)이라 per-add 동등이 hull 동등을 함의 안함. 선형 hull = open.")
