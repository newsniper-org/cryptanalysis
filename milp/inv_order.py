#!/usr/bin/env python3
"""Order of A and structure of the dim-1 residual at R=8; double-check reachability."""
import numpy as np
from inv_backbone import build_A, gf2_rank, matpow
from inv_ssm import C_xorsum, B_broadcast

A=build_A(); N=256
base=2**32-1   # 3*5*17*257*65537
I=np.eye(N,dtype=np.uint8)

def isI(M): return np.array_equal(M,I)

# order(A) must divide lcm(ord pieces). alpha^k powers: ord(alpha)=2^32-1, so per-lane
# alpha^{k_i} has order (2^32-1)/gcd(k_i,2^32-1). gcd with k in {1..9}: most are 1 except
# k where gcd>1. 2^32-1=3*5*17*257*65537. k=3 -> gcd 3; k=5->gcd5; k=6->gcd3; k=9->gcd3.
# So lane orders divide 2^32-1. Combined with pi (8-cycle on lanes) and rotations,
# order(A) | lcm(...). Test A^(8*base) and divisors.
print("=== order(A) probing ===")
for e_label,e in [("base",base),("8*base",8*base),("24*base",24*base),
                  ("8",8),("2",2),("3",3),("4",4)]:
    print(f"  A^({e_label}) == I ? {isI(matpow(A,e))}")

# minimal: order(A) = smallest t. Since alpha part dominates (~2^32), brute force is out.
# Instead: pick a generic vector v, find period of orbit under A (= ord of A restricted to
# cyclic subspace gen by v) by Berlekamp-Massey-free approach: smallest t with A^t v = v.
rng=np.random.default_rng(0)
v=rng.integers(0,2,size=N).astype(np.uint8)
# compute period by checking A^(d) v = v for divisors d of 8*base
def Apow_vec(e):
    M=matpow(A,e); return (M@v)%2
divs=[]
import itertools
fac={2:3,3:1,5:1,17:1,257:1,65537:1}  # 8*base = 2^3*3*5*17*257*65537
primes=[2,3,5,17,257,65537]; exps=[3,1,1,1,1,1]
def all_divs():
    ds=[1]
    for p,e in zip(primes,exps):
        ds=[d*p**k for d in ds for k in range(e+1)]
    return sorted(set(ds))
period=None
for d in all_divs():
    if np.array_equal(Apow_vec(d),v):
        period=d; break
print(f"\n  period of A on random vector v = {period}  (= order(A) if v cyclic-generic)")

# residual at R=8: the dim-1 ker(O_8) vector — what is it?
from inv_ssm import observability_Rstar
Cx=C_xorsum()
rows=[]; cur=Cx.copy()
for R in range(8): rows.append(cur.copy()); cur=(cur@A)%2
O8=np.vstack(rows)%2
# nullspace of O8
from inv_fixedspace import nullspace_basis, vec_to_state, hw_state
nb=nullspace_basis(O8)
print(f"\n  ker(O_8) dim={len(nb)} (the lone surviving GF(2)-linear inactive difference at R=8)")
for vec in nb:
    st=vec_to_state(vec)
    print(f"    survivor state={[hex(w) for w in st]} HW={hw_state(st)}")

# double-check reachability with explicit growth log
B=B_broadcast()
blocks=[B.copy()]; cur=B.copy(); print("\n=== reachability growth (rank of [B,AB,...,A^kB]) ===")
for k in range(12):
    Rmat=np.hstack(blocks)%2
    r=gf2_rank(Rmat.T)
    print(f"  k={k}: rank={r}")
    if r==N: break
    cur=(A@cur)%2; blocks.append(cur.copy())
