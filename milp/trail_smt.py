#!/usr/bin/env python3
"""
Bit-level 차분 트레일 활성-라운드 탐색 (z3 SMT-LIB 생성).

σ-GLM 라운드의 유일 비선형은 단어 S=⊕wᵢ 에 적용되는 F. F의 차분은
ΔF(δ)(s) = δ ⊕ G(s) ⊕ G(s⊕δ) 로, *입력차분 δ에 대해 s의 affine 함수*이며
F-차분 weight = rank(L_δ) (exact). 따라서 트레일 weight = Σ_r rank(L_{ΔS_r}).

본 스크립트는 z3로 "최소 활성 라운드 수 A(R)" 를 구한다(차분이 F를 회피 가능한
최대 라운드). 트레일 DP ≤ 2^(-w_min · A(R)),  w_min = min nonzero F-weight
(ypsilenti 2, yhash 4 — trail_fweight.py로 별도 정확 계산).

usage: python3 trail_smt.py <cipher> <R> <Kmax>   (cipher: ypsi|yhash)
z3 바이너리 필요.
"""
import sys, subprocess, tempfile, os

CIPHER = {
    "ypsi":  dict(n=32, w=8,  rot=(7,17,3,13),  red=0x400007,
                  sig=[(0,1),(4,3)],
                  P=[7,4,1,6,3,0,5,2]),
    "yhash": dict(n=64, w=16, rot=(13,37,5,23), red=0x1B,
                  sig=[(0,1),(4,3),(8,5),(12,7)],
                  P=[7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2]),
}

def bv(x, n): return f"(_ bv{x} {n})"

def rotl(term, k, n):
    k %= n
    if k == 0: return term
    return f"(bvor (bvshl {term} {bv(k,n)}) (bvlshr {term} {bv(n-k,n)}))"

def alpha(term, n, red):
    # mask = 0 - (x >> (n-1));  alpha = (x<<1) ^ (mask & red)
    top = f"(bvlshr {term} {bv(n-1,n)})"          # 0 or 1
    mask = f"(bvsub {bv(0,n)} {top})"             # 0 or all-ones
    return f"(bvxor (bvshl {term} {bv(1,n)}) (bvand {mask} {bv(red,n)}))"

def alpha_pow(term, k, n, red):
    t = term
    for _ in range(k): t = alpha(t, n, red)
    return t

def G(s, rot, n):
    a,b,c,d = rot
    return f"(bvxor (bvand {rotl(s,a,n)} {rotl(s,b,n)}) (bvand {rotl(s,c,n)} {rotl(s,d,n)}))"

def gen(cipher, R, K):
    cfg = CIPHER[cipher]
    n,w,rot,red,sig,P = cfg["n"],cfg["w"],cfg["rot"],cfg["red"],cfg["sig"],cfg["P"]
    L=[]
    L.append("(set-logic QF_BV)")
    # state difference vars: d_r_i  (round r, word i),  sf_r (free F point)
    for r in range(R+1):
        for i in range(w):
            L.append(f"(declare-fun d_{r}_{i} () (_ BitVec {n}))")
    for r in range(R):
        L.append(f"(declare-fun sf_{r} () (_ BitVec {n}))")
    # nonzero input
    nz = " ".join(f"(not (= d_0_{i} {bv(0,n)}))" for i in range(w))
    L.append(f"(assert (or {nz}))")
    # active indicators
    actterms=[]
    for r in range(R):
        # S = XOR words
        S = f"d_{r}_0"
        for i in range(1,w): S = f"(bvxor {S} d_{r}_{i})"
        L.append(f"(define-fun S_{r} () (_ BitVec {n}) {S})")
        # Dt = S ^ G(sf) ^ G(sf^S)
        Gs = G(f"sf_{r}", rot, n)
        Gsd = G(f"(bvxor sf_{r} S_{r})", rot, n)
        L.append(f"(define-fun Dt_{r} () (_ BitVec {n}) (bvxor (bvxor S_{r} {Gs}) {Gsd}))")
        # broadcast y_i = d_r_i ^ Dt ; sigma on sig lanes ; pi -> d_{r+1}
        ys=[]
        for i in range(w):
            yi = f"(bvxor d_{r}_{i} Dt_{r})"
            ys.append(yi)
        for (lane,k) in sig:
            ys[lane] = alpha_pow(ys[lane], k, n, red)
        for i in range(w):
            L.append(f"(assert (= d_{r+1}_{i} {ys[P[i]]}))")
        # active_r = (S != 0)
        L.append(f"(define-fun act_{r} () (_ BitVec 8) (ite (= S_{r} {bv(0,n)}) {bv(0,8)} {bv(1,8)}))")
        actterms.append(f"act_{r}")
    # sum of actives <= K
    tot = actterms[0]
    for t in actterms[1:]: tot=f"(bvadd {tot} {t})"
    L.append(f"(assert (bvule {tot} {bv(K,8)}))")
    L.append("(check-sat)")
    return "\n".join(L)

def run(cipher, R, K, timeout=120):
    smt = gen(cipher, R, K)
    with tempfile.NamedTemporaryFile("w", suffix=".smt2", delete=False) as f:
        f.write(smt); path=f.name
    try:
        out = subprocess.run(["z3","-T:%d"%timeout,path], capture_output=True, text=True, timeout=timeout+10)
        r = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "unknown"
    except subprocess.TimeoutExpired:
        r="timeout"
    finally:
        os.unlink(path)
    return r

def min_active(cipher, R, Kmax=8, timeout=120):
    for K in range(0, Kmax+1):
        res = run(cipher, R, K, timeout)
        if res == "sat":
            return K, "exact"
        if res in ("timeout","unknown"):
            return K, f"undetermined(>{K-1}, z3={res})"
    return Kmax+1, f">{Kmax}"

if __name__=="__main__":
    cipher = sys.argv[1] if len(sys.argv)>1 else "ypsi"
    R = int(sys.argv[2]) if len(sys.argv)>2 else 4
    Kmax = int(sys.argv[3]) if len(sys.argv)>3 else 8
    k, note = min_active(cipher, R, Kmax)
    wmin = 2 if cipher=="ypsi" else 4
    print(f"{cipher} R={R}: min_active_rounds A(R) = {k} ({note})  "
          f"=> trail DP <= 2^-{wmin*k}")
