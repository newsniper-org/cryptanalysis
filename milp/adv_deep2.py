import math
from adv_deep_prob1 import build, all_states, prob1_single_round_exact, best_DP, mk

cfgs=[
    ("n4w4 sigma{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
    ("n6w2 sigma{0}",   6,2,[1,1],2,[1,-1],[(0,1)],0x3,[1,0]),
]
print("=== (A) exact prob-1 single-round inactive set vs MSB-only lemma ===")
for name,n,w,rho,beta,eps,sig,red,P in cfgs:
    sv=prob1_single_round_exact(n,w,rho,beta,eps,sig,red,P)
    msb=1<<(n-1); M=(1<<n)-1
    non_msb=[(c,o) for c,o in sv if any(((c>>(i*n))&M)&(~msb&M) for i in range(w))]
    print(f"-- {name}: {len(sv)} prob-1 single-round inactive D; NON-MSB-bit ones (break lemma): {len(non_msb)}")
    for c,o in non_msb[:10]:
        Dw=tuple(hex((c>>(i*n))&M) for i in range(w)); print("      D=",Dw)

print()
print("=== (B) best iterated DP (high-prob non-prob-1 invariants) ===")
small=[
    ("n3w2", 3,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ("n4w2", 4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ("n4w4 sigma{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
]
for name,n,w,rho,beta,eps,sig,red,P in small:
    for R in ([1,2,3] if n*w<=8 else [1,2]):
        p,bd,bo=best_DP(n,w,rho,beta,eps,sig,red,P,R)
        l2=math.log2(p) if p>0 else float('-inf')
        print(f"  {name} R={R}: bestDP=2^{l2:.2f} ({p:.5f})  D={tuple(hex(z) for z in bd)} -> {tuple(hex(z) for z in bo)}")
