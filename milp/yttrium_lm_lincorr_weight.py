#!/usr/bin/env python3
"""
yttrium-LM 라운드당 선형 상관 weight (정확) — 비선형 원천별.

선형공격에서 corr(a,b)=E[(-1)^{a·x ⊕ b·f(x)}]. 라운드 함수의 선형 backbone(ROTL/ROTR/σ/π/ι)은
GF(2)-선형 → corr=1. corr<1을 만드는 비선형은 두 가산과 F 뿐.
선형 trail weight = -log2|corr| 가 라운드마다 누적. best(최소) weight 가 distinguisher 비용을 결정.

(W1) F의 best 선형 corr weight (정확 Walsh, n비트).
     F는 차분과 쌍대(transpose). 차분 min weight = w_F^diff (trail_fweight.py).
     선형 min weight w_F^lin: 모든 출력마스크 b!=0에 대해 max_a |corr_F(a,b)|, 그 max의 -log2.
     (단일 출력비트가 아니라 임의 b. Walsh로 각 b의 best-a를 정확히.)

(W2) 모듈러 가산 (broadcast x⊞t, and zero-sum reduction)의 선형 corr.
     Wallén/Nyberg: 가산 a+b=c 의 선형근사 corr = 2^{-(활성 carry chain 길이)}.
     단일 가산 best nonzero-mask corr weight ~ 1 (한 자리 carry). 그러나 trail에서
     마스크가 연쇄되면 누적. 여기선 reduction(8-입력 가산트리)와 broadcast의 최소 weight를
     소규모 가산(n=8,10)로 정확 Walsh 측정.

정직: F는 정확. 가산은 소규모 정확. 풀 라운드 hull 은 미증명(ARX SMT timeout).
라운드당 (F weight + 가산 weight) 하한으로 R 외삽.
"""
import numpy as np

def fwht_inplace(a):
    N = len(a); h = 1
    while h < N:
        for i in range(0, N, h*2):
            for j in range(i, i+h):
                x = a[j]; y = a[j+h]
                a[j] = x + y; a[j+h] = x - y
        h *= 2
    return a

def scale_terms(terms32, n):
    out = []
    for k in terms32:
        kk = max(1, round(k * n / 32)) % n
        if kk == 0: kk = 1
        out.append(kk)
    return out

# ---------- (W1) F best 선형 corr weight (모든 출력마스크 b, 정확) ----------
def F_best_lincorr(n, terms):
    """모든 b!=0 에 대해 max_a |corr_F(a,b)|; 반환: best over (a,b), and min over b of (best-a)."""
    M = (1 << n) - 1
    N = 1 << n
    xs = np.arange(N, dtype=np.int64)
    def rotl_arr(x, k):
        k %= n
        if k == 0: return x
        return ((x << k) | (x >> (n - k))) & M
    acc = np.zeros(N, dtype=np.int64)
    for i in range(0, len(terms), 2):
        acc ^= rotl_arr(xs, terms[i]) & rotl_arr(xs, terms[i+1])
    F = (xs ^ acc).astype(np.int64)
    best_overall = 0.0
    # min over b!=0 of (best over a of |corr|) — "어떤 출력비트조합도 corr 상한" 의 최댓값/최솟값
    best_per_b = np.zeros(N)
    for b in range(1, N):
        # g(x) = (-1)^{b·F(x)}
        fb = F & b
        par = np.zeros(N, dtype=np.int64)
        t = fb.copy()
        while t.any():
            par ^= (t & 1); t >>= 1
        g = (1 - 2*par).astype(np.float64)
        W = fwht_inplace(g.copy()) / N
        aW = np.abs(W)  # aW[a] = corr of (a·x) with b·F
        # a=0 허용 (a=0,b!=0 도 유효 선형근사). best over all a.
        bb = float(aW.max())
        best_per_b[b] = bb
        if bb > best_overall:
            best_overall = bb
    # min over b of best_per_b (모든 출력마스크에서 corr이 최소로 떨어지는 b — 방어상 중요)
    nz = best_per_b[1:]
    return best_overall, float(nz.max()), float(nz.min())

# ---------- (W2) 단일 모듈러 가산 z=(x+y) mod 2^n 의 best 선형 corr ----------
def add_best_lincorr(n):
    """가산의 best nonzero 선형근사 |corr|: 마스크 (mx,my->mz). 정확 (n<=10)."""
    N = 1 << n
    xs = np.arange(N, dtype=np.int64)
    best = 0.0; best_info = None
    # 출력마스크 mz 고정 -> g(x,y)=(-1)^{mz·((x+y)mod 2^n)} 의 입력선형 best
    # 2변수: 입력 (x,y) in N*N. FWHT over 2n bits.
    for mz in range(1, N):
        # 텐서: z = (x+y) mod N ; par_z = popcount(z & mz)&1
        X, Y = np.meshgrid(xs, xs, indexing='ij')
        Z = (X + Y) & (N-1)
        zb = Z & mz
        par = np.zeros_like(zb)
        t = zb.copy()
        while t.any():
            par ^= (t & 1); t >>= 1
        g = (1 - 2*par).astype(np.float64).reshape(-1)  # length N*N, index = x*N+y
        W = fwht_inplace(g.copy()) / (N*N)
        aW = np.abs(W)
        m = int(np.argmax(aW))
        if aW[m] > best:
            best = float(aW[m]); best_info = (mz, m>>n, m & (N-1))  # (mz, mx, my)
    return best, best_info

if __name__ == "__main__":
    terms32 = [7,17,3,21,9,29]
    print("###### (W1) F(S) best 선형 corr weight (정확 Walsh, 모든 출력마스크) ######")
    print("# corr_F(a,b)=E[(-1)^{a·x ⊕ b·F(x)}]. weight=-log2|corr|. F는 corr<1의 유일 nonlin(가산外).\n")
    for n in [8, 10, 12]:
        terms = scale_terms(terms32, n)
        bo, mx_overb, mn_overb = F_best_lincorr(n, terms)
        wbo = -np.log2(bo)
        wmin = -np.log2(mx_overb)   # 가장 corr 큰 b의 weight (=best_overall과 동일)
        wmax = -np.log2(mn_overb)   # 가장 corr 작은 b의 weight
        print(f"  n={n:2d} terms={terms}: best |corr_F| over all (a,b) = {bo:.5f} = 2^-{wbo:.3f}")
        print(f"           (출력마스크별 best-a corr: 최대 2^-{wmin:.3f}, 최소 2^-{wmax:.3f})")
    print()
    print("###### (W2) 단일 모듈러 가산 z=(x+y) best 선형 corr (정확) ######")
    print("# Wallén: 단일가산 best nonzero corr = 1/2 (weight 1). 검증.\n")
    for n in [6, 8]:
        b, info = add_best_lincorr(n)
        print(f"  n={n}: best |corr_add| = {b:.5f} = 2^-{-np.log2(b):.3f}  (mz=0x{info[0]:x}, mx=0x{info[1]:x}, my=0x{info[2]:x})")
