#!/usr/bin/env python3
"""
Adversarial prob1-subspace analysis (independent), full-size n=32.

Attack plan:
(A) Reproduce GF(2)-LA proxy inactive subspace at n=32 with distinct-rho; extract the actual
    basis differences; DIRECTLY measure their one-round additive Pr[ΔS=0] to test the author's
    "≈0.5, irrelevant" dismissal. If any basis diff passes with prob 1 (or close), the proxy is
    NOT irrelevant and a prob-1 subspace survives.
(B) Exact prob-1 MSB-inactive subspace at n=32 (the author's OWN lm_la model says MSB-only diffs
    pass the ⊞-broadcast with prob 1). Compute its dimension per R with the proposed distinct-rho
    framing. If dim>0 for R>=2, there is a genuine prob-1 invariant differential the design misses.
(C) Verify (B) survivors empirically: pick an MSB-inactive basis vector, push it through the REAL
    full round many times, measure Pr[output diff is the predicted constant] (prob-1 char check).
"""
import random
from adv_yttrium_check import build, make_alpha, make_F, mk, make_alpha_inv, N,W,RHO,EPS,SIGMA,PI,BETA,RED

def gf2_nullspace(cols, nvars):
    """Null space over GF(2) of matrix with given columns (image ints). Returns input-bit
       combinations (as ints) that map to zero."""
    rows=[(cols[k], 1<<k) for k in range(nvars)]
    basis=[]
    null=[]
    for img,comb in rows:
        cur_img=img; cur_comb=comb
        for (bimg,bcomb) in basis:
            hb=bimg.bit_length()-1
            if (cur_img>>hb)&1:
                cur_img^=bimg; cur_comb^=bcomb
        if cur_img==0:
            null.append(cur_comb)
        else:
            basis.append((cur_img,cur_comb))
            basis.sort(key=lambda t:-t[0].bit_length())
    return null

def proxy_inactive(n,w,rho,sigma,P,beta,red,R):
    m,rotl,rotr=mk(n); a=make_alpha(n,red)
    def apow(v,k):
        for _ in range(k): v=a(v)
        return v
    def words(s): return [(s>>(i*n))&m for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&m)<<(i*n)
        return s
    def Lin(s):
        ws=words(s)
        ws=[rotr(x,beta) for x in ws]
        for (ln,k) in sigma: ws[ln]=apow(ws[ln],k)
        return pack([ws[P[i]] for i in range(w)])
    def redsum(s):  # GF(2) proxy of zero-sum reduction
        ws=words(s); r=0
        for i in range(w): r^=rotl(ws[i],rho[i])
        return r
    Nb=n*w; cols=[]
    for k in range(Nb):
        cur=1<<k; col=0
        for r in range(R):
            col|=redsum(cur)<<(r*n); cur=Lin(cur)
        cols.append(col)
    return gf2_nullspace(cols,Nb), Nb

def msb_inactive(n,w,rho,sigma,P,beta,red,R):
    """Exact prob-1 additive-inactive subspace: MSB-only differences (add==xor at MSB),
       x-independent linear propagation, per-round non-MSB image zero + MSB sign-sum zero."""
    m,rotl,rotr=mk(n); a=make_alpha(n,red)
    def apow(v,k):
        for _ in range(k): v=a(v)
        return v
    def words(s): return [(s>>(i*n))&m for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&m)<<(i*n)
        return s
    def Lin(s):
        ws=words(s)
        ws=[rotr(x,beta) for x in ws]
        for (ln,k) in sigma: ws[ln]=apow(ws[ln],k)
        return pack([ws[P[i]] for i in range(w)])
    Nb=n*w; cols=[]; top=1<<(n-1); nonmsb=m^top
    for k in range(Nb):
        cur=1<<k; col=0; bp=0
        for r in range(R):
            ws=words(cur)
            for i in range(w):
                rot=rotl(ws[i],rho[i])
                col|=(rot & nonmsb)<<bp; bp+=n
            mx=0
            for i in range(w):
                rot=rotl(ws[i],rho[i]); mx^=(rot>>(n-1))&1
            col|=mx<<bp; bp+=1
            cur=Lin(cur)
        cols.append(col)
    return gf2_nullspace(cols,Nb), Nb

def measure_pass_additive(diff_int,n,w,trials):
    rnd,inv,Sval,m=build(n,w,RHO,EPS,SIGMA,PI,BETA,RED)
    D=tuple((diff_int>>(i*n))&m for i in range(w))
    hit=0
    for _ in range(trials):
        x=tuple(random.randint(0,m) for _ in range(w))
        if Sval(tuple(x[i]^D[i] for i in range(w)))==Sval(x): hit+=1
    return hit/trials, D

def measure_round_char(diff_int,n,w,trials):
    """Pr over random x that the REAL full round maps input-diff D to a single constant output
       diff (prob-1 differential). Returns (prob_of_modal_out, modal_out_diff, D)."""
    rnd,inv,Sval,m=build(n,w,RHO,EPS,SIGMA,PI,BETA,RED)
    D=tuple((diff_int>>(i*n))&m for i in range(w))
    cnt={}
    for _ in range(trials):
        x=tuple(random.randint(0,m) for _ in range(w))
        xd=tuple(x[i]^D[i] for i in range(w))
        od=tuple(rnd(x)[i]^rnd(xd)[i] for i in range(w))
        cnt[od]=cnt.get(od,0)+1
    modal=max(cnt,key=cnt.get)
    return cnt[modal]/trials, modal, D

if __name__=="__main__":
    random.seed(2026)
    print("=== (A) proxy inactive subspace n=32 distinct-rho, + additive pass-prob of basis ===")
    for R in [1,2,4,8,9]:
        null,Nb=proxy_inactive(N,W,RHO,SIGMA,PI,BETA,RED,R)
        print(f"  R={R}: proxy inactive dim={len(null)}")
    null2,_=proxy_inactive(N,W,RHO,SIGMA,PI,BETA,RED,2)
    print(f"  measuring additive 1-round Pr[ΔS=0] for up to 4 proxy-basis diffs at R=2:")
    for bi,comb in enumerate(null2[:4]):
        p,D=measure_pass_additive(comb,N,W,80000)
        print(f"    basis[{bi}] Pr[ΔS=0]={p:.4f}  Δ={[hex(d) for d in D]}")

    print()
    print("=== (B) EXACT prob-1 MSB-inactive subspace n=32 distinct-rho ===")
    Rstar=None
    for R in [1,2,3,4,5,6,8,10,12]:
        null,Nb=msb_inactive(N,W,RHO,SIGMA,PI,BETA,RED,R)
        if len(null)==0 and Rstar is None: Rstar=R
        print(f"  R={R}: prob-1 MSB-inactive dim={len(null)}")
    print(f"  => prob-1 MSB-inactive R* = {Rstar}")

    print()
    print("=== (C) empirical verification of an MSB-inactive survivor (R=2 and R=4) ===")
    for R in [2,4]:
        null,_=msb_inactive(N,W,RHO,SIGMA,PI,BETA,RED,R)
        if not null:
            print(f"  R={R}: no survivor"); continue
        diff=null[0]
        p1,D=measure_pass_additive(diff,N,W,200000)
        pc,modal,_=measure_round_char(diff,N,W,200000)
        print(f"  R={R}: survivor Δ={[hex(d) for d in D]}")
        print(f"        additive 1-round Pr[ΔS=0]={p1:.5f}")
        print(f"        real-round modal out-diff prob={pc:.5f}  (prob-1 char if ~1.0)")
