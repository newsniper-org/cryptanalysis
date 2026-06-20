#!/usr/bin/env python3
"""
Independent exact GF(2) propagation of the prob-1 MSB-inactive subspace at full n=32,w=8.

Model (justified by the MSB lemma): a differential passes the additive broadcast (u_i + t)
with probability 1 ONLY in the MSB position (add == xor at MSB, no carry out). For the
reduction S = sum eps_i ROTL_rho(x_i), a difference contributes to ΔS with prob 1 only
when ALL its set bits are MSBs (after ROTL_rho), and then the contribution is +-2^{n-1};
ΔS = 0 (mod 2^n) prob-1  iff  the signed sum of MSB contributions is even -> XOR of the
MSB bits across lanes = 0.

So the prob-1 inactive subspace at depth R is:
  { v != 0 : for every round r in 0..R-1,  Lin^r(v) has all non-MSB bits zero
             AND  the XOR of per-lane MSB bits of Lin^r(v) is 0 }
where Lin = pi o sigma o ROTR_beta o ROTL_rho is the LINEAR backbone.

This reproduces the author's model. We ADD adversarial cross-checks:
 (1) reproduce author's R* for sigma{0,4} and for all-lane.
 (2) CRITICAL: test whether the MSB lemma's linear backbone for sigma is right --
     sigma = GF alpha-mult is NOT GF(2)-linear-per-bit in the rotation sense? It IS
     GF(2)-linear (alpha-mult is a linear map over GF(2)^n). So we represent sigma as
     an explicit 32x32 GF(2) matrix per touched lane. This is EXACT, not an approximation.
 (3) Probe: place MSB-pairs ONLY on lanes NOT touched by sigma -> do they die at R=2?
"""

def make_alpha_mat(n,red):
    # alpha(x) = (x<<1) ^ (red if msb) ; as 32x32 GF(2) matrix (columns = images of basis e_k)
    # bit j of alpha(e_k):
    cols=[]
    for k in range(n):
        x=1<<k
        top=(x>>(n-1))&1
        y=((x<<1)&((1<<n)-1))^(red if top else 0)
        cols.append(y)
    # matrix as list of column-images; applying: y = XOR of cols[k] for set bits k
    return cols

def apply_mat(cols,x,n):
    y=0
    for k in range(n):
        if (x>>k)&1: y^=cols[k]
    return y & ((1<<n)-1)

def matpow(cols,k,n):
    # compose alpha matrix k times: result columns
    res=[1<<j for j in range(n)]  # identity columns
    base=cols
    for _ in range(k):
        res=[apply_mat(base,res[j],n) for j in range(n)]
    return res

def gf2_rank(vecs):
    basis=[]
    for v in vecs:
        cur=v
        for b in basis:
            cur=min(cur,cur^b)
        if cur:
            basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def lin_backbone(n,w,red,sigma,P,rho,beta):
    M=(1<<n)-1
    acols=make_alpha_mat(n,red)
    sig_mats={}
    for (lane,k) in sigma:
        sig_mats[lane]=matpow(acols,k,n)
    def rotl(x,kk):
        kk%=n
        return ((x<<kk)|(x>>(n-kk)))&M if kk else x
    def rotr(x,kk): return rotl(x,(n-(kk%n))%n)
    def words(state): return [(state>>(i*n))&M for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&M)<<(i*n)
        return s
    def Lin(state):
        ws=words(state)
        ws=[rotl(x,rho[i]) for i,x in enumerate(ws)]
        ws=[rotr(x,beta) for x in ws]
        for lane,mat in sig_mats.items():
            ws[lane]=apply_mat(mat,ws[lane],n)
        return pack([ws[P[i]] for i in range(w)])
    return Lin, words, M

def inactive_dim(n,w,red,sigma,P,rho,beta,R):
    Lin,words,M=lin_backbone(n,w,red,sigma,P,rho,beta)
    N=n*w
    msbmask = M ^ (1<<(n-1))
    cols=[]
    for k in range(N):
        cur=1<<k
        col=0; bp=0
        for r in range(R):
            ws=words(cur)
            for x in ws:
                col |= (x & msbmask) << bp; bp += n
            mx=0
            for x in ws: mx ^= (x>>(n-1))&1
            col |= mx << bp; bp += 1
            cur=Lin(cur)
        cols.append(col)
    return N - gf2_rank(cols)

def Rstar(name,n,w,red,sigma,P,rho,beta,Rmax):
    rs=None
    out=[]
    for R in range(1,Rmax+1):
        d=inactive_dim(n,w,red,sigma,P,rho,beta,R)
        out.append((R,d))
        if d==0 and rs is None: rs=R
        if d==0: break
    line=" ".join(f"R{R}:{d}" for R,d in out)
    print(f"  {name}: {line}  => R*={rs}")
    return rs

if __name__=="__main__":
    PI=[7,4,1,6,3,0,5,2]
    rho8=[8]*8
    red=0x400007  # author's primitive poly constant
    print("=== exact GF(2) MSB-inactive subspace, n=32 w=8, (rho,beta)=(8,9) ===")
    print("    sigma matrices computed EXACTLY as GF(2) alpha^k (32x32).")
    Rstar("sigma{0,4}=a^1,a^3 (minimal)", 32,8,red,[(0,1),(4,3)],PI,rho8,9,10)
    Rstar("sigma all-lane k=1..8",        32,8,red,[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)],PI,rho8,9,10)
    Rstar("sigma EMPTY (no orthomorphism)",32,8,red,[],PI,rho8,9,12)
    print()
    print("=== adversarial: vary beta to see if R*=2 is fragile ===")
    for b in [9,10,3,4,1]:
        Rstar(f"sigma{{0,4}} beta={b}", 32,8,red,[(0,1),(4,3)],PI,rho8,b,12)
    print()
    print("=== adversarial: what if pi were identity (isolate sigma+framing)? ===")
    Rstar("sigma{0,4} pi=id", 32,8,red,[(0,1),(4,3)],list(range(8)),rho8,9,14)
