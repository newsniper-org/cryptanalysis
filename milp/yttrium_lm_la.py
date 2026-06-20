#!/usr/bin/env python3
"""
yttrium Lai-Massey 가역 라운드 — 확률-1 (MSB-비활성) 부분공간 정확 경계 (GF(2) LA).

inactive_subspace.py 양식. 차이점:
  - reduction = 부호합(영합) S = Σ_i ε_i·ROTL_a(x_i)  (mod 2^n), Σε=0.
  - combiner = ROTR_b(ROTL_a(x_i) ⊞ t),  t=F(S)  (additive broadcast).
  - σ = GF(2^n) α-곱 (post-combiner), π = 워드 치환.

확률-1 비활성 차분의 *정확한* 집합(additive 차분 모델):
  공통 t의 가산은 GF(2)-선형이 아니므로, ΔS=0(=F 비활성)이어도 +t의 carry가 Δ를 섞는다.
  Δ가 확률 1로 가산을 '항등'으로 통과하는 비트는 **MSB 뿐**(add=xor at MSB). 따라서
  확률-1 비활성 부분공간 =
    { v≠0 : 각 라운드 r에서 Lin^r(v)의 비-MSB 비트 = 0  AND  MSB의 부호합(Δ) = 0 }
  Lin = π∘σ∘ROTR_b∘ROTL_a (선형 backbone). dim=0 되는 최소 R = R*.

OLD σ-GLM(XOR broadcast)과 동일 harness로 비교(그쪽은 xorsum=0 제약, framing 없음 → R*=w).
정직: 이 모델은 확률-1 (MSB) 부분에 대한 *정확* 경계. carry가 활성인 trail의 가중치는
별도(GPU best-DP, arx_gpu_refine.cu).
"""

def make_alpha(n, red):
    M = (1 << n) - 1
    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))
    return alpha

def gf2_rank(cols):
    basis = []
    for v in cols:
        cur = v
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def lin_factory(n, w, red, sigma, P, a, b, framing=True):
    M = (1 << n) - 1
    alpha = make_alpha(n, red)
    def alfp(v, k):
        for _ in range(k): v = alpha(v)
        return v
    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x
    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)
    def words(state): return [(state >> (i * n)) & M for i in range(w)]
    def pack(ws):
        s = 0
        for i, x in enumerate(ws): s |= (x & M) << (i * n)
        return s
    def Lin(state):
        ws = words(state)
        if framing:
            ws = [rotl(x, a) for x in ws]
            ws = [rotr(x, b) for x in ws]
        for (lane, k) in sigma:
            ws[lane] = alfp(ws[lane], k)
        return pack([ws[P[i]] for i in range(w)])
    return Lin, words, M

def inactive_dim_msb(n, w, red, sigma, P, a, b, R, framing=True):
    """확률-1 MSB-비활성 부분공간 차원 (additive 차분 모델)."""
    Lin, words, M = lin_factory(n, w, red, sigma, P, a, b, framing)
    N = n * w
    cols = []
    for k in range(N):
        cur = 1 << k
        col = 0; bp = 0
        for r in range(R):
            ws = words(cur)
            # (a) 비-MSB 비트는 0이어야 (확률-1 통과 = MSB만 허용)
            for x in ws:
                col |= (x & (M ^ (1 << (n - 1)))) << bp; bp += n
            # (b) MSB의 부호합 차분 = XOR of MSB bits = 0
            mx = 0
            for x in ws: mx ^= (x >> (n - 1)) & 1
            col |= mx << bp; bp += 1
            cur = Lin(cur)
        cols.append(col)
    return N - gf2_rank(cols)

def sweep_new(name, n, w, red, sigma, P, a, b, Rmax, framing=True):
    N = n * w
    print(f"== {name} (state {N} bit = {w}x{n})  a={a} b={b} framing={framing} ==")
    Rstar = None
    for R in range(1, Rmax + 1):
        d = inactive_dim_msb(n, w, red, sigma, P, a, b, R, framing)
        tag = ""
        if d == 0 and Rstar is None:
            Rstar = R; tag = "  <- R* (prob-1 MSB-inactive 소멸)"
        print(f"  R={R:2d}: dim(prob-1 inactive) = {d:4d}{tag}")
        if d == 0:
            break
    print(f"  => R* = {Rstar}")
    return Rstar

# ---- OLD σ-GLM (XOR broadcast) 비교 harness (inactive_subspace.py와 동일 정의) ----
def sweep_old_glm(name, n, w, red, sigma, P, Rmax):
    M = (1 << n) - 1; alpha = make_alpha(n, red)
    def alfp(v, k):
        for _ in range(k): v = alpha(v)
        return v
    def words(s): return [(s >> (i * n)) & M for i in range(w)]
    def pack(ws):
        s = 0
        for i, x in enumerate(ws): s |= (x & M) << (i * n)
        return s
    def Lin(s):
        ws = words(s)
        for (lane, k) in sigma: ws[lane] = alfp(ws[lane], k)
        return pack([ws[P[i]] for i in range(w)])
    def xorsum(s):
        r = 0
        for x in words(s): r ^= x
        return r
    N = n * w; Rstar = None
    print(f"== OLD GLM {name} (N={N}) ==")
    for R in range(1, Rmax + 1):
        cols = []
        for k in range(N):
            cur = 1 << k; col = 0
            for r in range(R):
                col |= xorsum(cur) << (r * n); cur = Lin(cur)
            cols.append(col)
        d = N - gf2_rank(cols); tag = ""
        if d == 0 and Rstar is None: Rstar = R; tag = "  <- R*"
        print(f"  R={R:2d}: dim = {d:4d}{tag}")
        if d == 0: break
    print(f"  => OLD R* = {Rstar}")
    return Rstar

if __name__ == "__main__":
    PI = [7, 4, 1, 6, 3, 0, 5, 2]
    SIG = [(0, 1), (4, 3)]              # σ 레인 0(α¹),4(α³)
    # NEW yttrium-LM, 실제 n=32 폭, 설계 회전 (a,b)=(8,9), red 0x400007 (primitive)
    sweep_new("yttrium-LM n=32 (a,b)=(8,9)", 32, 8, 0x400007, SIG, PI, 8, 9, 8)
    print()
    # 기여 분리(정직): framing 없이 σ만 / framing+σ
    sweep_new("ablation: sigma only (no framing)", 32, 8, 0x400007, SIG, PI, 0, 0, 8, framing=False)
    print()
    # OLD σ-GLM 재현 (repo R*=8)
    sweep_old_glm("yttrium n=32 (repo)", 32, 8, 0x400007, SIG, PI, 12)
    print()
    # yhash/u64 대응 (n=64, w=16). red·σ는 inactive_subspace.py와 동일 가정.
    sweep_new("yttrium-LM n=64 (a,b)=(8,9)", 64, 16, 0x1B,
              [(0, 1), (4, 3), (8, 5), (12, 7)],
              [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2], 8, 9, 8)
