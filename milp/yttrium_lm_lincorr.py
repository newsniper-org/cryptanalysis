#!/usr/bin/env python3
"""
yttrium-LM 선형 상관(linear correlation) 감쇠 측정 — 차분과 별개 척도.

목표: best 선형 근사 |corr| = |2*Pr[a·x = b·P_R(x)] - 1| 의 라운드별 감쇠.
선형 공격(distinguisher) 관점에서 R_b/R_c가 필요한 라운드 추정.

비선형 원천 두 가지만 corr<1:
  (1) modular add (zero-sum reduction S=Σεᵢx'ᵢ, broadcast x'ᵢ⊞t)  -> carry 선형근사
  (2) F(S) = S ⊕ (S⋘7 ∧ S⋘17) ⊕ (S⋘3 ∧ S⋘21) ⊕ (S⋘9 ∧ S⋘29)  -> AND 선형근사
σ(GF α^k), π, ROTL/ROTR, ι(RC) 는 모두 GF(2)-선형 → corr=1 (선형 backbone에 흡수).

축소폭(reduced width) n비트/레인 (n=8,12,16), w=8 레인 사용:
  - F의 회전상수는 mod n으로 스케일(원형 구조 보존). 가산은 mod 2^n.
  - n=8: F를 정확 Walsh로 단일출력비트 corr 측정 가능(2^8).
  - 전체 R라운드: 무작위 마스크쌍 (a입력,b출력) 다수 + 입력샘플로 |corr| 추정(경험적 상한).
정직: 경험적 corr은 floor가 1/sqrt(샘플수). 절대 hull 경계 아님. 라운드당 기울기 외삽.
"""
import numpy as np

def F_scalar(s, n, terms):
    M = (1 << n) - 1
    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x
    acc = 0
    for i in range(0, len(terms), 2):
        acc ^= rotl(s, terms[i]) & rotl(s, terms[i+1])
    return (s ^ acc) & M

def scale_terms(terms32, n):
    # 원래 (7,17,3,21,9,29) 회전상수를 n비트로 스케일(round, mod n, 0회전 회피)
    out = []
    for k in terms32:
        kk = max(1, round(k * n / 32)) % n
        if kk == 0: kk = 1
        out.append(kk)
    return out

# ---------- (1) F의 단일출력비트 best 선형 corr (정확 Walsh, n비트) ----------
def F_walsh_best_corr(n, terms):
    M = (1 << n) - 1
    N = 1 << n
    xs = np.arange(N, dtype=np.int64)
    # F 출력 (벡터화)
    def rotl_arr(x, k):
        k %= n
        if k == 0: return x
        return ((x << k) | (x >> (n - k))) & M
    acc = np.zeros(N, dtype=np.int64)
    for i in range(0, len(terms), 2):
        acc ^= rotl_arr(xs, terms[i]) & rotl_arr(xs, terms[i+1])
    F = xs ^ acc  # 출력
    best = 0.0
    best_ab = None
    # 입력마스크 a, 출력마스크 b 전수(2^n x 2^n) — n<=12까지만 전수, 그 외 샘플
    if n <= 11:
        A = np.arange(N, dtype=np.int64)
        for b in range(N):
            fb = F & b
            par_f = np.zeros(N, dtype=np.int64)
            t = fb.copy()
            while t.any():
                par_f ^= (t & 1); t >>= 1
            for a in range(N):
                ax = xs & a
                par_a = np.zeros(N, dtype=np.int64)
                t = ax.copy()
                while t.any():
                    par_a ^= (t & 1); t >>= 1
                agree = np.count_nonzero(par_a == par_f)
                corr = abs(2.0 * agree / N - 1.0)
                if corr > best and (a != 0 or b != 0):
                    best = corr; best_ab = (a, b)
    return best, best_ab

# 더 빠른 정확 Walsh (단일 출력비트만, 모든 입력마스크): n<=16
def F_walsh_single_outbit(n, terms, outbit):
    M = (1 << n) - 1
    N = 1 << n
    xs = np.arange(N, dtype=np.uint32)
    def rotl_arr(x, k):
        k %= n
        if k == 0: return x
        return ((x << k) | (x >> (n - k))) & M
    acc = np.zeros(N, dtype=np.uint32)
    for i in range(0, len(terms), 2):
        acc ^= rotl_arr(xs, terms[i]) & rotl_arr(xs, terms[i+1])
    F = xs ^ acc
    fbit = ((F >> outbit) & 1).astype(np.int64)   # 0/1
    f = 1 - 2 * fbit                                # +-1
    # Walsh: 모든 입력선형 a 와 f의 상관 = WHT. f를 자연순서로 두고 FWHT.
    a = f.astype(np.float64).copy()
    h = 1
    while h < N:
        for i in range(0, N, h*2):
            for j in range(i, i+h):
                x = a[j]; y = a[j+h]
                a[j] = x + y; a[j+h] = x - y
        h *= 2
    a /= N
    # a[mask] = corr of (mask·x) with f-as-+-1 ... best over mask!=0
    aa = np.abs(a.copy())
    aa[0] = 0.0
    bestmask = int(np.argmax(aa))
    return float(aa[bestmask]), bestmask

if __name__ == "__main__":
    terms32 = [7,17,3,21,9,29]
    print("###### (1) F(S)의 best 선형 상관 (단일 출력비트, 정확 Walsh) ######")
    print("# F = s ^ (s<<<r1 & s<<<r2) ^ ... ; 회전 mod n 스케일. corr<1의 유일 비선형(F)\n")
    for n in [8, 10, 12, 14, 16]:
        terms = scale_terms(terms32, n)
        best_over_bits = 0.0; bb = None
        for ob in range(n):
            c, m = F_walsh_single_outbit(n, terms, ob)
            if c > best_over_bits:
                best_over_bits = c; bb = (ob, m)
        wt = -np.log2(best_over_bits) if best_over_bits > 0 else float('inf')
        print(f"  n={n:2d} terms(rot)={terms}: best |corr| single-outbit = {best_over_bits:.5f} = 2^-{wt:.3f}  (outbit={bb[0]}, inmask=0x{bb[1]:x})")
