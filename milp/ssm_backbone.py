#!/usr/bin/env python3
"""yttrium SSM backbone: GF(2)-linear core A eigenstructure (F inactive, t=0)."""
N=256; W=8; RED=0x400007
SIG_K=[1,2,3,4,5,6,7,9]
P_PI=[7,4,1,6,3,0,5,2]
ROT_A=8; ROT_B=9
MASK32=(1<<32)-1

def rotl32(x,k):
    k%=32
    return ((x<<k)|(x>>(32-k)))&MASK32 if k else x&MASK32
def rotr32(x,k): return rotl32(x,(32-(k%32))%32)
def alpha(v):
    top=(v>>31)&1
    return (((v<<1)&MASK32)^(RED if top else 0))&MASK32
def apow(v,k):
    for _ in range(k): v=alpha(v)
    return v
def lane_bit(i,b): return i*32+b

def build_A_columns():
    cols=[]
    for j in range(N):
        wi,bi=divmod(j,32)
        word_val=1<<bi
        xp=rotl32(word_val,ROT_A)
        y=rotr32(xp,ROT_B)
        y=apow(y,SIG_K[wi])
        inv=P_PI.index(wi)
        out=0
        for b in range(32):
            if (y>>b)&1: out|=1<<lane_bit(inv,b)
        cols.append(out)
    return cols

def apply_cols(cols,v):
    out=0; vv=v; j=0
    while vv:
        if vv&1: out^=cols[j]
        vv>>=1; j+=1
    return out
def mat_mul(A,B): return [apply_cols(A,B[j]) for j in range(N)]
def mat_pow(A,e):
    R=[1<<j for j in range(N)]; base=A
    while e:
        if e&1: R=mat_mul(R,base)
        base=mat_mul(base,base); e>>=1
    return R
def is_identity(M): return all(M[j]==(1<<j) for j in range(N))
def gf2_rank_intcols(cols):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

if __name__=="__main__":
    A=build_A_columns()
    print("== yttrium GF(2) backbone A = pi.sigma.ROTR9.ROTL8 (t=0) ==")
    r=gf2_rank_intcols(A)
    print(f"rank(A) = {r}  (invertible: {r==N})")
    A8=mat_pow(A,8)
    blockdiag=True; offending=None
    for j in range(N):
        wi=j//32; col=A8[j]
        outwords=set((b//32) for b in range(N) if (col>>b)&1)
        if outwords and outwords!={wi}:
            blockdiag=False; offending=(j,wi,outwords); break
    print(f"A^8 block-diagonal per-lane: {blockdiag}  {offending if offending else ''}")
