#!/usr/bin/env python3
"""
yttrium-LM 전체 라운드 best 선형 상관(linear correlation) — 축소폭 경험적 측정.

라운드 P (yttrium, reduced width n비트/레인, w=8):
  ι:   x[r mod 8] ^= RC[r]          (선형, corr=1)
  red: xp_i = ROTL_a(x_i); S = Σ ε_i xp_i (mod 2^n), ε=[+,-,+,-,+,-,+,-]  (가산: carry 비선형)
  cmb: t = F(S); y_i = ROTR_b(xp_i ⊞ t)                                    (가산: carry 비선형)
  σ:   y_i = α^{k_i}·y_i (GF(2^n))   (선형, corr=1)
  π:   new_i = y_{P[i]}              (선형, corr=1)

선형 공격: 입력선형마스크 a, 출력선형마스크 b 에 대해
  corr(a,b) = (2/M) Σ_x (-1)^{a·x ⊕ b·P_R(x)} - ... = E_x[(-1)^{a·x ⊕ b·P_R(x)}].
best |corr| 가 2^-(n*w/2) (=128bit이면 2^-64) 보다 충분히 작아야 선형 distinguisher 불가.
누산/digest에서 R_b/R_c 합성이 이를 달성.

측정: a,b 무작위(저무게 우선) 다수 + 입력샘플 M개로 |corr| 추정.
 floor ≈ 1/sqrt(M). n작게(8) + 샘플 많이 → R당 감쇠 기울기 외삽.
정직: 경험적 상한. 절대 linear-hull 경계 아님(ARX hull은 SMT timeout, 도구한계).
"""
import numpy as np

PI = [7,4,1,6,3,0,5,2]
EPS = np.array([1,-1,1,-1,1,-1,1,-1], dtype=np.int64)
# 비반복 RC (SHA256 K 일부) — 선형이라 corr 무관, 그래도 라운드별 다르게
RC32 = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
        0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3]

def scale_terms(terms32, n):
    out = []
    for k in terms32:
        kk = max(1, round(k * n / 32)) % n
        if kk == 0: kk = 1
        out.append(kk)
    return out

def make_perm(n, w, red, sigk, a, b, terms):
    M = np.uint64((1 << n) - 1)
    Mpy = (1 << n) - 1
    nn = np.uint64(n)
    def rotl(x, k):
        k %= n
        if k == 0: return x
        kk = np.uint64(k); nk = np.uint64(n-k)
        return ((x << kk) | (x >> nk)) & M
    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)
    # GF(2^n) alpha
    topbit = np.uint64(1 << (n-1))
    redv = np.uint64(red)
    def alpha(x):
        top = (x >> np.uint64(n-1)) & np.uint64(1)
        return ((x << np.uint64(1)) & M) ^ (np.where(top == 1, redv, np.uint64(0)))
    def alfp(x, k):
        for _ in range(k):
            x = alpha(x)
        return x
    def Fvec(s):
        acc = np.zeros_like(s)
        for i in range(0, len(terms), 2):
            acc ^= rotl(s, terms[i]) & rotl(s, terms[i+1])
        return s ^ acc
    def perm(state, R):
        # state: (w, Nsamp) uint64 array
        ws = state.copy()
        for r in range(R):
            # ι
            ws[r % 8] = ws[r % 8] ^ np.uint64(RC32[r % len(RC32)] & Mpy)
            # red
            xp = [rotl(ws[i], a) for i in range(w)]
            S = np.zeros_like(ws[0])
            for i in range(w):
                if EPS[i] > 0:
                    S = (S + xp[i]) & M
                else:
                    S = (S - xp[i]) & M
            t = Fvec(S)
            y = [rotr((xp[i] + t) & M, b) for i in range(w)]
            # σ
            for i in range(w):
                if sigk[i]:
                    y[i] = alfp(y[i], sigk[i])
            # π
            ws = np.stack([y[PI[i]] for i in range(w)], axis=0)
        return ws
    return perm, Mpy

def parity_words(words_arr, masks):
    # words_arr: (w, Nsamp) uint64; masks: list of w ints
    acc = np.zeros(words_arr.shape[1], dtype=np.uint64)
    for i in range(words_arr.shape[0]):
        acc ^= words_arr[i] & np.uint64(masks[i])
    # parity
    par = np.zeros(words_arr.shape[1], dtype=np.int64)
    t = acc.copy()
    while t.any():
        par ^= (t & np.uint64(1)).astype(np.int64)
        t >>= np.uint64(1)
    return par  # 0/1

def best_corr(perm, n, w, R, Nsamp, n_masks, rng, low_weight=True):
    Mpy = (1 << n) - 1
    # 입력 샘플
    state = rng.integers(0, 1 << n, size=(w, Nsamp), dtype=np.uint64)
    out = perm(state, R)
    best = 0.0; best_info = None
    for _ in range(n_masks):
        if low_weight:
            # 저무게 마스크: 각 레인에 0 또는 single-bit, 1~3 레인 활성
            amask = [0]*w; bmask = [0]*w
            na = rng.integers(1, 3); nb = rng.integers(1, 3)
            for _ in range(na):
                amask[rng.integers(0,w)] |= (1 << rng.integers(0,n))
            for _ in range(nb):
                bmask[rng.integers(0,w)] |= (1 << rng.integers(0,n))
        else:
            amask = [int(rng.integers(0, 1<<n)) for _ in range(w)]
            bmask = [int(rng.integers(0, 1<<n)) for _ in range(w)]
        if all(m==0 for m in amask) or all(m==0 for m in bmask):
            continue
        pa = parity_words(state, amask)
        pb = parity_words(out, bmask)
        agree = np.count_nonzero(pa == pb)
        corr = abs(2.0 * agree / Nsamp - 1.0)
        if corr > best:
            best = corr; best_info = (amask, bmask)
    return best, best_info

if __name__ == "__main__":
    terms32 = [7,17,3,21,9,29]
    rng = np.random.default_rng(12345)
    n = 8; w = 8; a, b = 8 % n, 9 % n
    if a == 0: a = 1
    sigk = [1,2,3,5,7,11,13,17]  # all-8 σ
    terms = scale_terms(terms32, n)
    perm, Mpy = make_perm(n, w, red=0x1B, sigk=sigk, a=a, b=b, terms=terms)
    Nsamp = 1 << 22  # 4M samples -> floor ~2^-11
    floor = 1.0/np.sqrt(Nsamp)
    print(f"###### yttrium-LM reduced-width best |corr| (n={n}, w={w}, state={n*w}bit) ######")
    print(f"# (a,b)=({a},{b}) all-8 σ k={sigk}, terms(rot)={terms}")
    print(f"# Nsamp=2^{int(np.log2(Nsamp))} -> noise floor |corr|~{floor:.5f}=2^-{-np.log2(floor):.1f}")
    print(f"# 저무게 마스크 우선 탐색. 경험적 상한(=하한 추정), 절대경계 아님.\n")
    for R in range(1, 7):
        nm = 4000 if R <= 3 else 8000
        best, info = best_corr(perm, n, w, R, Nsamp, nm, rng, low_weight=True)
        wt = -np.log2(best) if best > 0 else float('inf')
        flag = "  (<= noise floor; corr 측정불가, 실제 더 작음)" if best <= floor*2.5 else ""
        print(f"  R={R}: best |corr| ~ {best:.6f} = 2^-{wt:.2f}{flag}")
