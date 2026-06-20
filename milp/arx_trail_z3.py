#!/usr/bin/env python3
"""
ARX(Amaryllises) 차분 trail 탐색기 — SMT-LIB2 생성 + z3 바이너리.

라운드(ypsilenti 8×u32):  S=⊕xᵢ ; t=F(S) ; broadcast yᵢ=ROTR_β(ROTL_α(xᵢ)⊞t) ; σ ; π.
차분 모델(표준 Markov/per-op):
  · F의 AND항: z=u∧v 차분 → 출력차분은 (Δu|Δv) 위치에서 free, weight = hw(Δu|Δv).
  · 모듈러 가산 c=a⊞b: Lipmaa–Moriai validity + weight = hw(((α⊕β)|(α⊕γ)) & 0x7fffffff).
  · σ(α-곱)·π: 선형(결정적, weight 0).
최소 trail weight = K를 0,1,2,… 증분 탐색(첫 SAT). DP_best = 2^-minweight.
σ-GLM(XOR broadcast)는 가산 없음 → baseline(대조). z3 바이너리 필요.

usage: python3 arx_trail_z3.py
"""
import subprocess, tempfile, os
N=32; ADDMASK=0x7fffffff; RED=0x400007; P_PI=[7,4,1,6,3,0,5,2]; ARX_L,ARX_R=8,3

def bv(x): return f"(_ bv{x} 32)"
def rotl(e,k):
    k%=N
    return e if k==0 else f"(bvor (bvshl {e} {bv(k)}) (bvlshr {e} {bv(N-k)}))"
def rotr(e,k): return rotl(e,(N-k)%N)
def alpha(e):
    mask=f"(bvsub {bv(0)} (bvand (bvlshr {e} {bv(31)}) {bv(1)}))"
    return f"(bvxor (bvshl {e} {bv(1)}) (bvand {mask} {bv(RED)}))"
def alpha_pow(e,k):
    for _ in range(k): e=alpha(e)
    return e

class SMT:
    def __init__(s): s.L=["(set-logic QF_BV)"]; s.W=[]; s.n=0
    def fresh(s,pfx):
        s.n+=1; v=f"{pfx}{s.n}"; s.L.append(f"(declare-fun {v} () (_ BitVec 32))"); return v
    def assert_(s,e): s.L.append(f"(assert {e})")
    def popcount_w(s,expr):
        # weight var(16bit) = popcount(expr)
        s.n+=1; w=f"w{s.n}"; s.L.append(f"(declare-fun {w} () (_ BitVec 16))")
        bits=" ".join(f"((_ zero_extend 15) ((_ extract {i} {i}) {expr}))" for i in range(N))
        s.L.append(f"(assert (= {w} (bvadd {bits})))")
        s.W.append(w); return w

def build(rounds, terms, sigma, combiner, K):
    s=SMT()
    # round-0 state diffs
    dx=[s.fresh("dx0_") for _ in range(8)]
    nz=" ".join(f"(not (= {d} {bv(0)}))" for d in dx)
    s.assert_(f"(or {nz})")
    for r in range(rounds):
        # S = XOR
        S=dx[0]
        for i in range(1,8): S=f"(bvxor {S} {dx[i]})"
        Sv=s.fresh("S_"); s.assert_(f"(= {Sv} {S})")
        # F: t = S ^ XOR_k dz_k ; weight hw(rotl(S,p)|rotl(S,q))
        dzs=[]
        for (p,q) in terms:
            active=f"(bvor {rotl(Sv,p)} {rotl(Sv,q)})"
            dz=s.fresh("dz_")
            s.assert_(f"(= (bvand {dz} (bvnot {active})) {bv(0)})")  # 출력차분은 활성위치만
            s.popcount_w(active)
            dzs.append(dz)
        t=Sv
        for dz in dzs: t=f"(bvxor {t} {dz})"
        tv=s.fresh("t_"); s.assert_(f"(= {tv} {t})")
        # broadcast
        outs=[]
        for i in range(8):
            if combiner=='xor':
                outs.append(f"(bvxor {dx[i]} {tv})")
            else:  # arx: gamma = rotl(dx,L) ⊞ t (Lipmaa-Moriai), then rotr(.,R)
                a=rotl(dx[i],ARX_L); b=tv
                g=s.fresh("g_")
                # validity: eq(a<<1,b<<1,g<<1) & (a^b^g^(b<<1)) == 0
                a1=f"(bvshl {a} {bv(1)})"; b1=f"(bvshl {b} {bv(1)})"; g1=f"(bvshl {g} {bv(1)})"
                eqv=f"(bvand (bvnot (bvxor {a1} {b1})) (bvnot (bvxor {a1} {g1})))"
                cond=f"(bvxor (bvxor (bvxor {a} {b}) {g}) {b1})"
                s.assert_(f"(= (bvand {eqv} {cond}) {bv(0)})")
                # weight = hw( ((a^b)|(a^g)) & 0x7fffffff )
                noneq=f"(bvand (bvor (bvxor {a} {b}) (bvxor {a} {g})) {bv(ADDMASK)})"
                s.popcount_w(noneq)
                outs.append(rotr(g,ARX_R))
        # sigma (α^k on lanes)
        ov=[s.fresh("o_") for _ in range(8)]
        for i in range(8): s.assert_(f"(= {ov[i]} {outs[i]})")
        for (lane,k) in sigma:
            so=s.fresh("so_"); s.assert_(f"(= {so} {alpha_pow(ov[lane],k)})"); ov[lane]=so
        # pi -> next dx
        ndx=[s.fresh(f"dx{r+1}_") for _ in range(8)]
        for i in range(8): s.assert_(f"(= {ndx[i]} {ov[P_PI[i]]})")
        dx=ndx
    # total weight <= K  (weight 합은 16-bit)
    if s.W:
        tot=s.W[0]
        for w in s.W[1:]: tot=f"(bvadd {tot} {w})"
        s.assert_(f"(bvule {tot} (_ bv{K} 16))")
    s.L.append("(check-sat)")
    return "\n".join(s.L)

def run(smt, timeout=90):
    with tempfile.NamedTemporaryFile("w",suffix=".smt2",delete=False) as f:
        f.write(smt); p=f.name
    try:
        r=subprocess.run(["z3",f"-T:{timeout}",p],capture_output=True,text=True,timeout=timeout+10)
        out=(r.stdout or "").strip().splitlines()
        return out[0] if out else "unknown"
    except subprocess.TimeoutExpired: return "timeout"
    finally: os.unlink(p)

def min_weight(rounds, terms, sigma, combiner, Kmax=24, timeout=90):
    for K in range(0,Kmax+1):
        res=run(build(rounds,terms,sigma,combiner,K),timeout)
        if res=="sat": return K,"exact"
        if res in("timeout","unknown"): return K,f"undet(>{K-1},z3={res})"
    return Kmax+1,f">{Kmax}"

F3=[(7,17),(3,21),(9,29)]; F4=F3+[(5,27)]; F2o=[(7,17),(3,13)]
S2=[(0,1),(4,3)]; S4=[(0,1),(2,5),(4,3),(6,7)]
CFG=[
 ("[baseline] σ-GLM XOR 2-term(원본) σ{0,4}",'xor',F2o,S2),
 ("ARX 3-term σ{0,4}",'arx',F3,S2),
 ("ARX 4-term σ{0,4}",'arx',F4,S2),
 ("ARX 3-term σ{0,2,4,6}",'arx',F3,S4),
 ("ARX 4-term σ{0,2,4,6}",'arx',F4,S4),
]
ROUNDS=[1,2,3]
if __name__=="__main__":
    print("최소 trail weight (= -log2 best-DP; 높을수록 강함). 'undet'=z3 timeout 하한.\n")
    print(f"{'config':<40}"+"".join(f" R={r:<10}" for r in ROUNDS))
    for name,comb,terms,sig in CFG:
        row=f"{name:<40}"
        for r in ROUNDS:
            k,note=min_weight(r,terms,sig,comb)
            tag=f"{k}" if note=="exact" else f"{k}({note})"
            row+=f" {tag:<11}"
        print(row, flush=True)
