#!/usr/bin/env python3
"""
Adversarial part 2: test the ACTUAL proposed full-size lane structure (w=8) at small n,
and the proposed ρ=[0,5,11,17,23,3,13,29], ε=[+,-,...], σ on lanes {0,2,4,6} with k=1,3,5,7,
red 0x400007 reduced to small n.

CRITICAL invertibility subtlety: σ is applied AFTER ROTR_beta and BEFORE pi. The inversion
must undo σ before recovering S (because S is recovered from v_i = ROTL_beta(y_i) where y_i
is PRE-sigma). The proposal's inversion step 2 does σ^{-1} before step 3 (ROTL_beta). Good.

But there's a deeper question: does the zero-sum recovery actually need σ to be a permutation,
or could a NON-permutation σ still give a permutation round by luck? And: is the round still a
permutation if we use the EXACT proposed w=8 lane assignment at small n? Test n=2,w=8 (16-bit
state, 65536 -> full exhaustive).
"""
import random
from adv_invert import build_round, make_alpha, mk

def test_perm_full(n,w,rho,beta,eps,sigma,red,P, limit_bits=22):
    rnd,rnd_inv,Sval,M=build_round(n,w,rho,beta,eps,sigma,red,P)
    total=1<<(n*w)
    if total>(1<<limit_bits):
        # sample roundtrip only
        bad=0
        for _ in range(50000):
            st=tuple(random.randint(0,M) for _ in range(w))
            if rnd_inv(rnd(st))!=st: bad+=1
        return ("roundtrip-sample", bad, 50000)
    seen=set()
    for c in range(total):
        st=tuple((c>>(i*n))&M for i in range(w))
        seen.add(rnd(st))
    return ("full", len(seen), total)

if __name__=="__main__":
    random.seed(3)
    # n must be >= 1; small-n reduction polynomials for GF(2^n):
    # n=2: x^2+x+1 -> red 0x3 ; n=4: x^4+x+1 -> 0x3 ; n=5: x^5+x^2+1 -> 0x5
    # Proposal uses w=8 lanes with sigma on {0,2,4,6} k={1,3,5,7}.
    SIG=[(0,1),(2,3),(4,5),(6,7)]
    PPI=[7,4,1,6,3,0,5,2]
    EPS=[1,-1,1,-1,1,-1,1,-1]
    # full proposed rho but reduced mod n for tiny n
    RHO_full=[0,5,11,17,23,3,13,29]

    print("=== w=8 full-structure, alternate n (rho mod n, red small) ===")
    for n,red in [(2,0x3),(3,0x3),(4,0x3),(5,0x5)]:
        rho=[r%n for r in RHO_full]
        beta=2%n if n>2 else 1
        res=test_perm_full(n,8,rho,beta,EPS,SIG,red,PPI, limit_bits=24)
        print(f"  n={n} w=8 state={n*8}b rho(modn)={rho} beta={beta} red={hex(red)}: {res}")

    # Now specifically check: is sigma even a permutation for these reduced reds?
    print("\n=== sigma (alpha^k) permutation check at small n ===")
    for n,red in [(2,0x3),(3,0x3),(4,0x3),(5,0x5),(8,0x1D),(16,0x2B)]:
        a=make_alpha(n,red)
        img={a(x) for x in range(1<<n)}
        is_perm = len(img)==(1<<n)
        # check alpha^7 too
        def apow(x,k):
            for _ in range(k): x=a(x)
            return x
        img7={apow(x,7) for x in range(1<<n)}
        print(f"  n={n} red={hex(red)}: alpha perm={is_perm}  alpha^7 perm={len(img7)==(1<<n)}")
