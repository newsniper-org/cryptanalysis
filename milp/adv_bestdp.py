import math
from adv_deep_prob1 import build, all_states

def best_DP(n,w,rho,beta,eps,sigma,red,P,R):
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    states=list(all_states(n,w))
    img={x:x for x in states}
    for _ in range(R):
        img={x:rnd(img[x]) for x in states}
    M=(1<<n)-1; total=1<<(n*w); best=0; bd=None; bo=None
    for cD in range(1,total):
        D=tuple((cD>>(i*n))&M for i in range(w)); cnt={}
        for x in states:
            xd=tuple(x[i]^D[i] for i in range(w))
            od=tuple(img[x][i]^img[xd][i] for i in range(w))
            cnt[od]=cnt.get(od,0)+1
        mx=max(cnt.values())
        if mx>best: best=mx; bd=D; bo=max(cnt,key=cnt.get)
    return best/total, bd, bo

print("=== best iterated DP over ALL nonzero diffs (small-n exhaustive) ===")
print("    if best 2R/3R DP stays near 1, R*=2 (prob-1 metric) is misleading.")
cfgs=[
    ("n3w2", 3,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ("n4w2", 4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ("n4w4 sigma{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
]
for name,n,w,rho,beta,eps,sig,red,P in cfgs:
    Rs=[1,2,3,4] if n*w<=8 else [1,2]
    for R in Rs:
        p,bd,bo=best_DP(n,w,rho,beta,eps,sig,red,P,R)
        l2=math.log2(p) if p>0 else float('-inf')
        print(f"  {name} R={R}: bestDP=2^{l2:.2f} ({p:.5f}) D={tuple(hex(z) for z in bd)} -> {tuple(hex(z) for z in bo)}")
