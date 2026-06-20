import random
from adv_deep_prob1 import build, mk

# Targeted prob-1 check at n=6,w=4 (24-bit state): exhaustive over MSB-only diff set (2^4 patterns
# per the 'all bits must be MSB' lemma) but verify over MANY random x whether ANY non-MSB diff
# can be prob-1 inactive that the LA would miss. We sample diffs broadly + verify over all x for
# small subsets.
def is_prob1_round(rnd,n,w,D,states):
    out0=None
    for x in states:
        xd=tuple(x[i]^D[i] for i in range(w))
        od=tuple(rnd(x)[i]^rnd(xd)[i] for i in range(w))
        if out0 is None: out0=od
        elif od!=out0: return False,None
    return True,out0

# n=5,w=4 (20-bit) full exhaustive over states for a CURATED diff list (can't do all 2^20 diffs x 2^20 states)
n,w=5,4; rho=[1,1,1,1]; beta=2; eps=[1,-1,1,-1]; sig=[(0,1),(2,3)]; red=0x5; P=[3,0,1,2]
rnd,m=build(n,w,rho,beta,eps,sig,red,P)
msb=1<<(n-1); M=(1<<n)-1
states=[tuple((c>>(i*n))&M for i in range(w)) for c in range(1<<(n*w))]
print(f"n={n} w={w}: checking prob-1 over all 2^{n*w} states for curated diffs", flush=True)

# 1) all MSB-only diffs (each lane in {0, ROTR_rho(msb)} so post-ROTL it's MSB). rho=1 -> input bit that becomes MSB = msb>>1
inbit = (msb>>1)  # ROTL_1 of this = msb
cur_surv=[]
for pat in range(1,16):
    D=tuple(inbit if (pat>>i)&1 else 0 for i in range(w))
    ok,o=is_prob1_round(rnd,n,w,D,states)
    if ok: cur_surv.append((D,o))
print(f"  MSB-pattern prob-1 survivors (round-1): {len(cur_surv)} (expect even-parity subset, dim w-1=3 -> 7)")

# 2) random NON-MSB diffs: do ANY pass prob-1? (search for lemma violation)
random.seed(5); viol=0; tested=0
for _ in range(4000):
    D=tuple(random.randint(0,M) for _ in range(w))
    if all(x==0 for x in D): continue
    # skip pure MSB-input patterns
    if all((x==0 or x==inbit) for x in D): continue
    tested+=1
    ok,o=is_prob1_round(rnd,n,w,D,states)
    if ok:
        viol+=1
        print(f"  *** NON-MSB prob-1 inactive diff FOUND: D={tuple(hex(z) for z in D)} -> {tuple(hex(z) for z in o)}")
print(f"  non-MSB diffs tested={tested}, prob-1 violations (lemma breaks)={viol}")

# 3) iterate the MSB survivors to R=2: do any stay prob-1?
def rnd2(st): return rnd(rnd(st))
surv2=0
for D,_ in cur_surv:
    out0=None; ok=True
    for x in states:
        xd=tuple(x[i]^D[i] for i in range(w))
        od=tuple(rnd2(x)[i]^rnd2(xd)[i] for i in range(w))
        if out0 is None: out0=od
        elif od!=out0: ok=False; break
    if ok and any(out0): surv2+=1
print(f"  MSB survivors still prob-1 at R=2: {surv2} (expect 0 => R*=2)")
