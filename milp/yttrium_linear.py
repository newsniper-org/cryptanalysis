#!/usr/bin/env python3
"""
yttrium 선형 상관(linear correlation) 감쇠 — best 선형 근사 |corr| 의 라운드별 감쇠.

배경(SPEC §10-C, milp/yttrium-round-count.md "차원: 선형상관"):
  선형 distinguisher / 선형 hull 은 |corr(a,b)| = |E_x[(-1)^{a·x ⊕ b·P_R(x)}]| 가
  검출한계(digest 128-bit → 2^-64, state 256-bit wide-pipe → 2^-128) 위로 살아남는 R 로
  라운드수를 제약한다. ARX 고유 "free-LSB"(가산 LSB→LSB corr=1) 가 framing/σ/π 에
  충분히 흩어지지 않으면 저무게 선형 trail 이 R_b/R_c 를 관통.

세 측정:
  (W1) F 의 best 선형 corr (정확). 풀폭 n=32 에서 출력비트 F_j = s_j ⊕ 3개 AND쌍 →
       비트당 AND 게이트 3개 → best 단일출력비트 corr = 2^-3 (정확).
  (W2) 단일 모듈러 가산 z=x+y 의 best 선형 corr (n<=8 정확 2변수 FWHT) → free-LSB(corr=1).
  (full) 축소폭(n=16/8) R라운드 |corr| 경험적 추정 (마스크쌍 (a,b) 탐색, 입력샘플 N).

정직 / 도구한계:
  * full 경험적 corr 은 noise floor ~ 1/sqrt(N) 에 R>=2 서 막힘 → slope 는 R1->R2 한 구간만 신뢰.
  * 마스크 탐색은 single-bit exhaustive + 저무게 랜덤뿐 → 진짜 best 멀티비트 trail/hull 은
    못 찾았을 수 있음(실제 corr 은 측정값 이상; 권고가 낙관적일 위험 → 보수적으로 잡음).
  * linear hull(다중 trail 보강) 미측정 = ARX SMT timeout 도구한계. 절대 경계 아님.
  * 풀폭 N=2^30급 Walsh distinguisher 는 GPU 몫(yttrium_lm_diff.cu 양식 fold→hist→corr).

실행: python3 yttrium_linear.py
"""
import numpy as np
import math
import itertools


# ---------- (W1) F 의 정확 선형 corr (풀폭 n=32, 비트국소 함수 전수) ----------
def F_linear_corr_exact():
    """풀폭 F: 출력비트 j = s_j ⊕ (s_{j+7}&s_{j+17}) ⊕ (s_{j+3}&s_{j+21}) ⊕ (s_{j+9}&s_{j+29}).
    한 출력비트는 7개 입력비트(자기 + 6 AND-피연산자)의 함수 → 2^7 전수 Walsh."""
    n = 32
    # 출력비트0 이 의존하는 입력비트(회전 오프셋): 0, 7,17, 3,21, 9,29
    deps = [0, 7, 17, 3, 21, 9, 29]
    # 7-변수 진리표 구축: vars 순서 = deps
    nv = len(deps)
    size = 1 << nv
    tt = np.zeros(size, dtype=np.int8)
    for x in range(size):
        bit = {}
        for vi, d in enumerate(deps):
            bit[d] = (x >> vi) & 1
        out = bit[0] ^ (bit[7] & bit[17]) ^ (bit[3] & bit[21]) ^ (bit[9] & bit[29])
        tt[x] = out
    # best linear corr over all input masks (output mask = 1, 단일 출력비트)
    f = 1 - 2 * tt.astype(np.float64)   # (-1)^out
    best = 0.0
    for a in range(1, size):
        # corr = E[(-1)^{a.x} * (-1)^out]
        par = np.zeros(size)
        for x in range(size):
            par[x] = bin(x & a).count("1") & 1
        s = np.mean((1 - 2 * par) * f)
        if abs(s) > best:
            best = abs(s)
    return best, -math.log2(best) if best > 0 else float("inf")


# ---------- (W2) 단일 모듈러 가산의 best 선형 corr (n<=8 정확) ----------
def add_linear_corr(n):
    M = (1 << n) - 1
    size = 1 << n
    # corr(mz; mx,my) = E_{x,y}[(-1)^{mx.x ⊕ my.y ⊕ mz.(x+y mod 2^n)}]
    # free-LSB: mx=my=mz=1 -> corr=1. 일반 best 는 작음.
    xs = np.arange(size)
    bestfree = 0.0
    for mz in (1,):   # LSB 출력마스크
        for mx in (1,):
            for my in (1,):
                tot = 0
                for x in range(size):
                    z = (x + xs) & M
                    par = (
                        np.array([bin((x & mx)).count("1") & 1])
                        ^ (np.array([bin(int(y) & my).count("1") & 1 for y in xs]))
                        ^ (np.array([bin(int(zz) & mz).count("1") & 1 for zz in z]))
                    )
                    tot += np.sum(1 - 2 * par)
                bestfree = tot / (size * size)
    return bestfree


# ---------- (full) 축소폭 R라운드 경험적 |corr| ----------
def find_primitive_red(n):
    M = (1 << n) - 1
    target = (1 << n) - 1
    for red in range(3, 1 << n, 2):
        v = 1
        ok = True
        for _ in range(1, target):
            top = v >> (n - 1)
            v = ((v << 1) & M) ^ (red if top else 0)
            if v == 1:
                ok = False
                break
        top = v >> (n - 1)
        v = ((v << 1) & M) ^ (red if top else 0)
        if ok and v == 1:
            return red
    raise RuntimeError("no primitive red")


def make_perm_np(n, w, red, sig_k, P, A, B, eps):
    M = (1 << n) - 1

    def rotl(x, k):
        k %= n
        return x & M if k == 0 else ((x << k) | (x >> (n - k))) & M

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alpha(v):
        top = (v >> (n - 1)) & 1
        return (((v << 1) & M) ^ (top * red)) & M

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    if n >= 8:
        TERMS = [(7 % n, 17 % n), (3 % n, 21 % n), (9 % n, 29 % n)]
    else:
        TERMS = [(1, n // 2), (2 % n or 1, n - 1), (3 % n or 1, (n - 2) % n or 1)]

    def F(s):
        acc = s.copy()
        for (p, q) in TERMS:
            acc = acc ^ (rotl(s, p) & rotl(s, q))
        return acc & M

    def rnd(state):
        xp = [rotl(state[i], A) for i in range(w)]
        S = np.zeros_like(xp[0])
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, B) for i in range(w)]
        y = [alfp(y[i], sig_k[i]) for i in range(w)]
        return [y[P[i]] for i in range(w)]

    def permute(state, R):
        s = list(state)
        for _ in range(R):
            s = rnd(s)
        return s

    return permute, M


def empirical_corr(n, w, red, sig_k, P, A, B, eps, R, N, seed=0, n_rand=3000):
    permute, M = make_perm_np(n, w, red, sig_k, P, A, B, eps)
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << n, size=N, dtype=np.uint64) for _ in range(w)]
    out = permute(x, R)

    def parity(words, masks):
        acc = np.zeros(N, dtype=np.uint64)
        for i in range(w):
            acc ^= (words[i].astype(np.uint64) & np.uint64(masks[i]))
        # XOR-fold popcount parity (log2(64) shifts, fully vectorized)
        v = acc.copy()
        v ^= v >> np.uint64(32)
        v ^= v >> np.uint64(16)
        v ^= v >> np.uint64(8)
        v ^= v >> np.uint64(4)
        v ^= v >> np.uint64(2)
        v ^= v >> np.uint64(1)
        return (v & np.uint64(1)).astype(np.int8)

    best = 0.0
    invN = 1.0 / N
    # single-bit exhaustive: stack parities into matrices, corr matrix = Pin^T Pout / N (one BLAS call)
    Pin = np.empty((w * n, N), dtype=np.float32)
    Pout = np.empty((w * n, N), dtype=np.float32)
    r = 0
    for il in range(w):
        for ib in range(n):
            m = [0] * w
            m[il] = 1 << ib
            Pin[r] = (1 - 2 * parity(x, m)).astype(np.float32)
            Pout[r] = (1 - 2 * parity(out, m)).astype(np.float32)
            r += 1
    C = (Pin @ Pout.T) * invN          # (wn x wn) correlation matrix
    best = float(np.max(np.abs(C)))
    # low-weight random masks (vectorized): build random mask parities, correlate against single-bit out
    if n_rand > 0:
        Pr_in = np.empty((n_rand, N), dtype=np.float32)
        Pr_out = np.empty((n_rand, N), dtype=np.float32)
        for k in range(n_rand):
            ain = [int(rng.integers(0, 1 << n)) if rng.random() < 0.4 else 0 for _ in range(w)]
            bout = [int(rng.integers(0, 1 << n)) if rng.random() < 0.4 else 0 for _ in range(w)]
            if all(v == 0 for v in ain):
                ain[0] = 1
            if all(v == 0 for v in bout):
                bout[0] = 1
            Pr_in[k] = (1 - 2 * parity(x, ain)).astype(np.float32)
            Pr_out[k] = (1 - 2 * parity(out, bout)).astype(np.float32)
        cr = np.abs(np.einsum("ij,ij->i", Pr_in, Pr_out) * invN)
        best = max(best, float(cr.max()))
    return best


def main():
    print("### yttrium 선형 상관(linear correlation) 감쇠 ###")
    print("# best |corr| 가 검출한계(digest 2^-64) 위로 살아남는 R 가 라운드수 제약\n")

    bf, bw = F_linear_corr_exact()
    print(f"(W1) F 풀폭 n=32 best 단일출력비트 선형 corr = {bf:.5f} = 2^-{bw:.2f}")
    print("     (출력비트당 AND 게이트 3개 → weight 3; 라운드당 활성 F-비트마다 +3 누적)\n")

    for n in (6, 8):
        c = add_linear_corr(n)
        print(f"(W2) 단일 모듈러 가산 n={n}: LSB-only mask corr = {c:.5f}  (free-LSB corr=1 확인)")
    print()

    # (full) reduced-width n=8 w=8 = 64-bit state, all-8 distinct-power sigma
    n, w = 8, 8
    red = find_primitive_red(n)
    P = [7, 4, 1, 6, 3, 0, 5, 2]
    SIGK = [1, 2, 3, 5, 7, 11, 13, 17]          # distinct powers (artifact 회피)
    eps = [1, -1, 1, -1, 1, -1, 1, -1]
    A, B = 8 % n, 9 % n
    N = 1 << 19
    print(f"(full) n={n} w={w} (state {n*w}-bit) all-8 distinct-σ red={hex(red)} (A,B)=({A},{B}), N={N}")
    print(f"       noise floor ~ 2^-{0.5*math.log2(N):.1f}")
    prev = None
    for R in range(1, 5):
        c = empirical_corr(n, w, red, SIGK, P, A, B, eps, R, N, seed=R)
        wgt = -math.log2(c) if c > 0 else float("inf")
        sl = "" if prev is None else f"  dW=+{wgt-prev:.2f}"
        print(f"  R={R}: best|corr|=2^-{wgt:.2f}{sl}")
        prev = wgt
    print("\n정직: R>=2 는 noise floor 제약 → slope 는 R1->R2 한 구간만 신뢰. 멀티비트 best-trail/")
    print("      hull 은 미탐(실제 corr 은 측정 이상일 수). 풀폭 Walsh distinguisher 는 GPU 몫.")


if __name__ == "__main__":
    main()
