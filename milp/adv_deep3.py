import math
from adv_deep_prob1 import build, all_states, mk

def prob1_single(n,w,rho,beta,eps,sigma,red,P):
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    states=list(all_states(n,w))
    # precompute rnd for all states once
    img={x:rnd(x) for x in states}
    M=(1<<n)-1; total=1<<(n*w); sv=[]
    for cD in range(1,total):
        D=tuple((cD>>(i*n))&M for i in range(w))
        out0=None; ok=True
        for x in states:
            ox=img[x]; oxd=img[tuple(x[i]^D[i] for i in range(w))]
            od=tuple(ox[i]^oxd[i] for i in range(w))
            if out0 is None: out0=od
            elif od!=out0: ok=False; break
        if ok: sv.append((cD,out0))
    return sv

# only feasible sizes
cfgs=[
    ("n6w2 sigma{0}",   6,2,[1,1],2,[1,-1],[(0,1)],0x3,[1,0]),
    ("n4w4 sigma{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
]
print("=== (A) exact prob-1 single-round inactive set vs MSB-only lemma ===")
for name,n,w,rho,beta,eps,sig,red,P in cfgs:
    sv=prob1_single(n,w,rho,beta,eps,sig,red,P)
    msb=1<<(n-1); M=(1<<n)-1
    non_msb=[(c,o) for c,o in sv if any(((c>>(i*n))&M)&(~msb&M) for i in range(w))]
    print(f"-- {name}: {len(sv)} prob-1 single-round inactive D; NON-MSB-bit ones (break lemma): {len(non_msb)}")
    for c,o in sv[:12]:
        Dw=tuple(hex((c>>(i*n))&M) for i in range(w)); print("      D=",Dw,"-> out",tuple(hex(z) for z in o))
