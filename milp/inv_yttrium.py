#!/usr/bin/env python3
"""
yttrium NONLINEAR-INVARIANT / INVARIANT-SUBSPACE attack, exact frozen spec.

Frozen spec (yttrium/src/lib.rs):
  iota   : state[r%8] ^= RC[r]
  framing: x'_i = ROTL_8(x_i)
  reduce : S = sum_i eps_i x'_i (mod 2^n),  eps=[+,-,+,-,+,-,+,-]
  F      : t = F(S) = S ^ (S<<<7 & S<<<17) ^ (S<<<3 & S<<<21) ^ (S<<<9 & S<<<29)
  ARX    : y_i = ROTR_9(x'_i + t)
  sigma  : y_i <- alpha^{k_i} y_i,  k=[1,2,3,4,5,6,7,9], GF(2^32) red 0x400007
  pi     : new[i] = y[P[i]],  P=[7,4,1,6,3,0,5,2]

This module provides a SCALED round R_n (word width n bits, 8 lanes) that preserves
the structural shape. For n<32 the F rotations and alpha reduction are scaled
sensibly; the n=32 instance is bit-exact to the spec. We use it for:
  - exhaustive nonlinear-invariant search (small n, few lanes)
  - prob-1 invariant subspace under the affine round
  - exact GF(2) backbone matrix construction (carry-aware reduction as a GF(2) map
    is NOT linear; we build the linear part = framing/ROTR/sigma/pi and treat the
    additive reduction+F via its difference behaviour).
"""

# ---- frozen spec constants (n=32) ----
P_PI   = [7,4,1,6,3,0,5,2]
EPS    = [1,-1,1,-1,1,-1,1,-1]
SIG_K  = [1,2,3,4,5,6,7,9]
ROT_A  = 8     # framing ROTL
ROT_B  = 9     # ARX ROTR
F_ROT  = [(7,17),(3,21),(9,29)]
RED32  = 0x400007

SHA256_K = [
 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]

def rc32(r):
    return SHA256_K[r] if r < 64 else (SHA256_K[r%64] ^ r)

# ---------- generic n-bit round (structural scale) ----------
class Yt:
    def __init__(self, n, red, frot, rota=ROT_A%None if False else None, rotb=None,
                 sig_k=None, use_rc=True):
        self.n = n
        self.M = (1<<n)-1
        self.red = red
        self.frot = frot
        self.rota = (rota if rota is not None else (ROT_A % n if n<32 else ROT_A))
        self.rotb = (rotb if rotb is not None else (ROT_B % n if n<32 else ROT_B))
        self.sig_k = sig_k if sig_k is not None else SIG_K
        self.use_rc = use_rc
    def rotl(self,x,k):
        k%=self.n
        return ((x<<k)|(x>>(self.n-k)))&self.M if k else x&self.M
    def rotr(self,x,k):
        return self.rotl(x,(self.n-(k%self.n))%self.n)
    def alpha(self,v):
        top = v>>(self.n-1)
        return ((v<<1)&self.M)^(self.red if top else 0)
    def alpha_pow(self,v,k):
        for _ in range(k): v=self.alpha(v)
        return v
    def F(self,s):
        acc=s
        for (a,b) in self.frot:
            acc ^= self.rotl(s,a)&self.rotl(s,b)
        return acc&self.M
    def reduce(self,xp):
        s=0
        for i in range(8):
            if EPS[i]>0: s=(s+xp[i])&self.M
            else:        s=(s-xp[i])&self.M
        return s
    def round(self, state, r):
        st=list(state)
        if self.use_rc:
            st[r%8]^= (rc32(r)&self.M)
        xp=[self.rotl(st[i],self.rota) for i in range(8)]
        s=self.reduce(xp); t=self.F(s)
        y=[0]*8
        for i in range(8):
            v=self.rotr((xp[i]+t)&self.M, self.rotb)
            y[i]=self.alpha_pow(v, self.sig_k[i])
        return [y[P_PI[i]] for i in range(8)]
    def perm(self, state, R):
        st=list(state)
        for r in range(R): st=self.round(st,r)
        return st

def yt32():
    return Yt(32, RED32, F_ROT, ROT_A, ROT_B, SIG_K, use_rc=True)

if __name__=="__main__":
    # sanity: 32-bit round invertibility-shape check vs reference behaviour
    y=yt32()
    st=[0x01234567,0x89abcdef,0xdeadbeef,0xcafebabe,1,2,3,0xffffffff]
    out=y.perm(st,8)
    print("yt32 perm(8) sample:", [hex(z) for z in out])
