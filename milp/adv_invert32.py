import random
from adv_invert import build_round, test_permutation

random.seed(12345)
# FULL n=32, w=8 roundtrip with minimal sigma{0,4} and all-lane sigma, real rotations.
PI=[7,4,1,6,3,0,5,2]
rho8=[8]*8
configs=[
    ("n32w8 sigma{0,4}=a1,a3 (8,9)", 32,8,rho8,9,[1,-1,1,-1,1,-1,1,-1],[(0,1),(4,3)],0x400007,PI),
    ("n32w8 sigma all k=1..8 (8,9)", 32,8,rho8,9,[1,-1,1,-1,1,-1,1,-1],[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)],0x400007,PI),
]
print("=== invertibility: full n=32 w=8 roundtrip (random states + random RC) ===")
for name,n,w,rho,beta,eps,sig,red,P in configs:
    RC=[random.randint(0,(1<<32)-1) for _ in range(64)]
    rnd,rinv,Sval,M=build_round(n,w,rho,beta,eps,sig,red,P,RC)
    bad=0; ex=None
    for _ in range(50000):
        st=tuple(random.randint(0,M) for _ in range(w)); r=random.randint(0,200)
        o=rnd(st,r); back=rinv(o,r)
        if back!=st:
            bad+=1
            if ex is None: ex=(st,r)
    print(f"  {name}: 50000 roundtrips, mismatches={bad}  ex={ex}")

# multi-round roundtrip (6 rounds) to be sure composition is invertible
print()
print("=== 6-round composition roundtrip ===")
for name,n,w,rho,beta,eps,sig,red,P in configs:
    RC=[random.randint(0,(1<<32)-1) for _ in range(64)]
    rnd,rinv,Sval,M=build_round(n,w,rho,beta,eps,sig,red,P,RC)
    bad=0
    for _ in range(20000):
        st=tuple(random.randint(0,M) for _ in range(w))
        cur=st
        for r in range(6): cur=rnd(cur,r)
        for r in range(5,-1,-1): cur=rinv(cur,r)
        if cur!=st: bad+=1
    print(f"  {name}: 20000 6-round roundtrips, mismatches={bad}")
