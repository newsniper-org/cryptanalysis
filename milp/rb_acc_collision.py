#!/usr/bin/env python3
"""
R_b 차원 — acc-충돌(8-way XOR generalized birthday) 정량 분석 (소규모).

acc-충돌 공격 모델 (farfalle-tree-design.md §보안분석, unkeyed):
  leaf: acc = ⊕_{j<n<=8} P_b(block_j ⊕ mask_j),  mask_j 공개(공격자 계산가능).
  digest 동일을 위해 acc 동일을 노린다. block 차분 Δ_j 를 슬롯들에 주입,
  P_b(R_b) 통과 후 출력차분이 8개 슬롯에서 XOR-상쇄(=0)되면 acc 충돌.
  => 핵심 비용 = "한 슬롯에서 입력차분 Δ → 출력차분 ∇ 의 DP" 와 8-way XOR(Wagner)의 결합.

본 파일은 단일 슬롯 P_b 의 best-DP 를 (i) n=32 full-word 경험적 표본,
(ii) n=8 / n=16 축소폭 *완전(exact)* DP 로 측정해 라운드당 weight 기울기를 잡는다.
n축소는 GPU(N=2^30, floor~2^-25)가 못 보는 깊은 라운드의 정확 DP를 보기 위함.

라운드 = yttrium LM (yttrium_lm_diff.cu / SPEC §6) 그대로:
  xp_i = ROTL_a(x_i); S=Σ ε_i xp_i (ε=[+,-,...]); t=F(S);
  y_i = ROTR_b(xp_i + t); y_i = α^{k_i} y_i; π.
RC(ι)는 XOR 주입 → 차분 투명, DP 분석에서 생략(표준).
"""
import random

# ---- field / rotate helpers, parametric width n ----
def make_ops(n, red):
    M = (1 << n) - 1
    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M
    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)
    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))
    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v
    return M, rotl, rotr, alfp

# F rotation offsets scaled from n=32 (7,17,3,21,9,29) — keep distinct mod n.
def make_F(n, rotl):
    if n == 32:
        terms = [(7,17),(3,21),(9,29)]
    elif n == 16:
        terms = [(3,9),(1,11),(5,15)]
    elif n == 8:
        terms = [(1,4),(2,6),(3,7)]
    else:
        terms = [(1, n//2)]
    def F(s):
        acc = s
        for (p,q) in terms:
            acc ^= rotl(s,p) & rotl(s,q)
        return acc
    return F

EPS = [1,-1,1,-1,1,-1,1,-1]
PI  = [7,4,1,6,3,0,5,2]

def make_round(n, red, a, b, sigk):
    M, rotl, rotr, alfp = make_ops(n, red)
    F = make_F(n, rotl)
    def rnd(state):
        xp = [rotl(state[i], a) for i in range(8)]
        S = 0
        for i in range(8):
            S = (S + xp[i]) % (1<<n) if EPS[i] > 0 else (S - xp[i]) % (1<<n)
        t = F(S)
        y = [rotr((xp[i] + t) & M, b) for i in range(8)]
        y = [alfp(y[i], sigk[i]) for i in range(8)]
        return [y[PI[i]] for i in range(8)]
    return rnd, M

def permute(state, R, rnd):
    s = list(state)
    for _ in range(R):
        s = rnd(s)
    return s

# ---- empirical best-DP for a fixed input difference, single slot, n=32 ----
def emp_dp(delta, R, rnd, M, n, samples):
    from collections import Counter
    c = Counter()
    for _ in range(samples):
        x = [random.getrandbits(n) for _ in range(8)]
        y = [x[i] ^ delta[i] for i in range(8)]
        ox = permute(x, R, rnd)
        oy = permute(y, R, rnd)
        d = tuple(ox[i] ^ oy[i] for i in range(8))
        c[d] += 1
    top = c.most_common(1)[0][1]
    return top / samples

if __name__ == "__main__":
    import math
    random.seed(1)
    print("=== (1) n=32 single-slot empirical best-DP, MSB zero-sum pairs (acc-collision relevant) ===")
    print("    (block 차분이 한 슬롯 P_b 통과; acc 상쇄엔 동일 출력차가 두 슬롯서 나야)\n")
    SIGK = [1,2,3,5,7,11,13,17]
    rnd32, M32 = make_round(32, 0x400007, 8, 9, SIGK)
    # MSB zero-sum same-sign pairs: the deltas yttrium_lm_diff.cu flagged as worst
    plus=[0,2,4,6]; minus=[1,3,5,7]
    msb = 1<<31
    deltas = []
    for a_ in range(4):
        for b_ in range(a_+1,4):
            d=[0]*8; d[plus[a_]]=msb; d[plus[b_]]=msb; deltas.append(("plus-pair",tuple(d)))
    # single-bit reference
    d=[0]*8; d[0]=1; deltas.append(("1bit-lsb",tuple(d)))
    d=[0]*8; d[0]=msb; deltas.append(("1bit-msb",tuple(d)))
    SAMPLES=200000
    for R in (1,2,3):
        best=0; bestname=None
        for name,d in deltas:
            p=emp_dp(d,R,rnd32,M32,32,SAMPLES)
            if p>best: best=p; bestname=name
        w = -math.log2(best) if best>0 else 999
        floor = -math.log2(1/SAMPLES)
        print(f"  R={R}: worst-δ best-DP ≈ 2^-{w:.1f}  ({bestname})   [sample floor 2^-{floor:.1f}]")
