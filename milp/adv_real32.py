#!/usr/bin/env python3
"""
Adversarial invertibility at the REAL parameters: n=32, w=8, rho=[0,5,11,17,23,3,13,29],
beta=9, eps=[+,-,...], sigma lanes {0,2,4,6} k={1,3,5,7}, red=0x400007, P=[7,4,1,6,3,0,5,2],
RC = SHA256 K[r]. Sampled roundtrip (full state space 2^256 not exhaustible).

ALSO: verify the zero-sum identity sum eps_i v_i == S holds EXACTLY at n=32 on random inputs
(this is the load-bearing claim). If it ever fails, invertibility is broken.

ALSO: check red=0x400007 is primitive (ord(alpha)=2^32-1) and alpha^k XOR-orthomorphism at n=32
(sampled, since 2^32 full is too big -- but XOR-ortho can be checked structurally:
alpha^k ^ I as a 32x32 GF(2) matrix must be invertible).
"""
import random, hashlib, struct

SHA256_K = [
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]

M=0xFFFFFFFF
def rotl(x,k): k&=31; return ((x<<k)|(x>>(32-k)))&M if k else x&M
def rotr(x,k): return rotl(x,(32-(k&31))&31)
def F(s):
    return (s ^ (rotl(s,7)&rotl(s,17)) ^ (rotl(s,3)&rotl(s,21)) ^ (rotl(s,9)&rotl(s,29)))&M
RED=0x400007
def alpha(v): return (((v<<1)&M)^(RED if (v>>31)&1 else 0))
# alpha^{-1}: solve. alpha is mult by x; inverse is mult by x^{-1}. Build via matrix or via
# the relation: if we know forward map, invert per-bit. Easiest: alpha is GF(2)-linear, build
# 32x32 matrix and invert.
def alpha_matrix():
    cols=[]
    for j in range(32):
        cols.append(alpha(1<<j))
    return cols  # cols[j] = alpha(e_j)
ACOLS=alpha_matrix()
def alpha_apply_mat(cols,x):
    r=0
    for j in range(32):
        if (x>>j)&1: r^=cols[j]
    return r&M
def mat_inv(cols):
    # invert 32x32 over GF(2): augment [A | I], cols are columns of A as ints (bit i = row i)
    # Represent as rows for elimination.
    A=[0]*32; Iaug=[0]*32
    for i in range(32):
        row=0
        for j in range(32):
            if (cols[j]>>i)&1: row|=1<<j
        A[i]=row; Iaug[i]=1<<i
    for col in range(32):
        piv=None
        for r in range(col,32):
            if (A[r]>>col)&1: piv=r;break
        assert piv is not None
        A[col],A[piv]=A[piv],A[col]; Iaug[col],Iaug[piv]=Iaug[piv],Iaug[col]
        for r in range(32):
            if r!=col and (A[r]>>col)&1:
                A[r]^=A[col]; Iaug[r]^=Iaug[col]
    # now Iaug rows form inverse matrix rows; convert to columns-int form
    invcols=[0]*32
    for i in range(32):
        for j in range(32):
            if (Iaug[i]>>j)&1: invcols[j]|=1<<i
    return invcols
AINVCOLS=mat_inv(ACOLS)
def alpha_inv(x): return alpha_apply_mat(AINVCOLS,x)
def apow(x,k):
    for _ in range(k): x=alpha(x)
    return x
def apow_inv(x,k):
    for _ in range(k): x=alpha_inv(x)
    return x

RHO=[0,5,11,17,23,3,13,29]; BETA=9; EPS=[1,-1,1,-1,1,-1,1,-1]
SIG=[(0,1),(2,3),(4,5),(6,7)]; PPI=[7,4,1,6,3,0,5,2]

def Sval(st):
    s=0
    for i in range(8): s=(s+EPS[i]*rotl(st[i],RHO[i]))&M
    return s
def rnd(st,r):
    w=list(st); w[r%8]^=SHA256_K[r%64]; w[r%8]&=M
    u=[rotl(w[i],RHO[i]) for i in range(8)]
    S=0
    for i in range(8): S=(S+EPS[i]*u[i])&M
    t=F(S)
    v=[(u[i]+t)&M for i in range(8)]
    y=[rotr(v[i],BETA) for i in range(8)]
    for (ln,k) in SIG: y[ln]=apow(y[ln],k)
    return tuple(y[PPI[i]] for i in range(8)), S, v
def rnd_inv(out,r):
    y=[0]*8
    for i in range(8): y[PPI[i]]=out[i]
    for (ln,k) in SIG: y[ln]=apow_inv(y[ln],k)
    v=[rotl(y[i],BETA) for i in range(8)]
    Srec=0
    for i in range(8): Srec=(Srec+EPS[i]*v[i])&M
    t=F(Srec)
    u=[(v[i]-t)&M for i in range(8)]
    w=[rotr(u[i],RHO[i]) for i in range(8)]
    w[r%8]^=SHA256_K[r%64]; w[r%8]&=M
    return tuple(w), Srec, v

if __name__=="__main__":
    random.seed(99)
    # alpha primitivity / orthomorphism at n=32
    # ord(alpha): too big to iterate fully fast, but check alpha^k XOR-ortho via matrix invertibility
    print("=== n=32 alpha checks ===")
    for k in [1,3,5,7]:
        # matrix of alpha^k
        cols=[apow(1<<j,k) for j in range(32)]
        # XOR-ortho: alpha^k(x) ^ x perm <=> (M_k + I) invertible
        cols_plus=[cols[j]^(1<<j) for j in range(32)]
        try:
            mat_inv(cols_plus); ortho=True
        except Exception: ortho=False
        print(f"  k={k}: alpha^k XOR-orthomorphism (M_k+I invertible) = {ortho}")
    # primitivity quick test: alpha^(2^32-1)=1 and alpha^((2^32-1)/p)!=1 for prime factors p
    # 2^32-1 = 3*5*17*257*65537
    one=1
    facs=[3,5,17,257,65537]
    n=(1<<32)-1
    def apow_fast(x,e):
        # repeated mult by matrix is slow; do exponentiation by composing alpha e times is huge.
        # Instead build matrix power. Use matrix exponentiation of ACOLS.
        return None
    print("  (primitivity: matrix-order check)")
    # matrix order via matrix exponentiation
    def matmul(a,b):
        # columns-int representation: (a∘b)(e_j) = a(b(e_j))
        return [alpha_apply_mat(a, b[j]) for j in range(32)]
    def matpow(c,e):
        R=[1<<j for j in range(32)]  # identity columns
        base=c[:]
        while e:
            if e&1: R=matmul(R,base)
            base=matmul(base,base); e>>=1
        return R
    full=matpow(ACOLS, n)
    isI = all(full[j]==(1<<j) for j in range(32))
    print(f"    alpha^(2^32-1)=I : {isI}")
    prim=isI
    for p in facs:
        sub=matpow(ACOLS, n//p)
        if all(sub[j]==(1<<j) for j in range(32)):
            prim=False; print(f"    alpha^((2^32-1)/{p})=I  -> NOT primitive")
    print(f"  => red=0x400007 primitive (ord alpha = 2^32-1): {prim}")

    print("\n=== zero-sum identity + roundtrip at n=32 (sampled) ===")
    bad_id=0; bad_rt=0; ex=None
    for _ in range(200000):
        st=tuple(random.getrandbits(32) for _ in range(8))
        r=random.randint(0,127)
        out,S,v=rnd(st,r)
        # identity: sum eps_i v_i == S
        chk=0
        for i in range(8): chk=(chk+EPS[i]*v[i])&M
        if chk!=S: bad_id+=1
        back,Srec,_=rnd_inv(out,r)
        if back!=st:
            bad_rt+=1
            if ex is None: ex=(st,r,back)
        if Srec!=S: bad_id+=1
    print(f"  zero-sum identity failures: {bad_id}/200000")
    print(f"  roundtrip mismatches:      {bad_rt}/200000  ex={ex}")
