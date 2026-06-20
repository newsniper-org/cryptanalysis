#!/usr/bin/env python3
"""
INDEPENDENT adversarial review of yttrium-LM-ARX proposal.
Faithful re-implementation of the round from `round_equations`, then attack:
  LENS = farfalle-bridge (primary) + prob1-subspace + invertibility cross-check.

Round (per proposal):
  ι  : state[r%w] ^= RC[r]
  red: x'_i = ROTL_a(state_i);  S = sum_i eps_i x'_i  (mod 2^n), sum eps=0
  t  = F(S)
  G  : y_i = ROTR_b( x'_i + t )
  σ  : y_i = alpha^{k_i} y_i  (GF mult) on selected lanes
  π  : new[i] = y[P[i]]
"""
import random, itertools

# ---------- primitives ----------
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_F(n,pairs=((7,17),(3,21),(9,29))):
    m,rotl,_=mk(n)
    pp=[((a%n),(b%n)) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp: acc ^= (rotl(s,a)&rotl(s,b))
        return acc&m
    return F

def alpha_factory(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

def make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,F=None):
    m,rotl,rotr=mk(n)
    if F is None: F=make_F(n)
    al=alpha_factory(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    ainv={al(x):x for x in range(1<<n)}
    def apow_inv(x,k):
        for _ in range(k): x=ainv[x]
        return x
    def rnd(state,rc=0,rc_lane=0):
        ws=list(state); ws[rc_lane]^=rc; ws[rc_lane]&=m
        u=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (ln,k) in sigma_lanes: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    def inv(state,rc=0,rc_lane=0):
        out=list(state); y=[0]*w
        for i in range(w): y[P[i]]=out[i]
        for (ln,k) in sigma_lanes: y[ln]=apow_inv(y[ln],k)
        v=[rotl(y[i],b_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&m for i in range(w)]
        ws=[rotr(u[i],a_rot) for i in range(w)]
        ws[rc_lane]^=rc; ws[rc_lane]&=m
        return tuple(ws)
    return rnd,inv,F

# =====================================================================
# LENS 1: prob1-subspace — find prob-1 inactive differentials NOT captured
#   by the MSB-only LA model. Key idea: ANY difference D=(d_0..d_{w-1})
#   such that for ALL states x, F(S(x)) == F(S(x+D)) leaves t unchanged.
#   If additionally the adder propagates D additively (carry-free for the
#   given pair) the round is affine on the pair. The MSB model only counts
#   D with d_i in {0, ROTR_a(MSB)}. We brute-force search small n for
#   prob-1 inactive D of OTHER shapes (multi-round).
# =====================================================================
def find_prob1_inactive_multiround(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,R,
                                    samples=4000, cand_weight=1):
    """For each candidate input difference D (low Hamming weight on the
    additive state), test whether rnd^R(x) XOR rnd^R(x+D) is CONSTANT over
    many random x (prob-1 differential through R rounds). Return such D."""
    m=(1<<n)-1
    rnd,inv,F=make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P)
    def addD(x,D): return tuple((x[i]+D[i])&m for i in range(w))  # additive diff
    def xorD(x,D): return tuple((x[i]^D[i]) for i in range(w))    # xor diff
    def Rrnd(x):
        for r in range(R): x=rnd(x,rc=0,rc_lane=0)
        return x
    hits=[]
    # candidate set: single-lane single-bit (xor) + MSB-pair lanes + the MSB add-diff
    cands=[]
    for ln in range(w):
        for bit in range(n):
            D=[0]*w; D[ln]=1<<bit; cands.append(("xor",tuple(D)))
    # additive MSB on a lane
    for ln in range(w):
        D=[0]*w; D[ln]=1<<(n-1); cands.append(("add",tuple(D)))
    # the proposal's "MSB-pair" prob-1 class: ROTR_a(MSB) on two even lanes (eps cancel)
    rl=mk(n)[1]
    msb_pre=mk(n)[2](1<<(n-1),a_rot)  # ROTR_a(2^{n-1}) so that ROTL_a brings it to MSB
    for (i,j) in itertools.combinations(range(w),2):
        D=[0]*w; D[i]=msb_pre; D[j]=msb_pre; cands.append(("add",tuple(D)))
    for kind,D in cands:
        if all(d==0 for d in D): continue
        const=None; ok=True
        for _ in range(samples):
            x=tuple(random.randint(0,m) for _ in range(w))
            x2=(addD if kind=="add" else xorD)(x,D)
            o1=Rrnd(x); o2=Rrnd(x2)
            d=tuple((o1[i]-o2[i])&m for i in range(w)) if kind=="add" else tuple(o1[i]^o2[i] for i in range(w))
            if const is None: const=d
            elif d!=const: ok=False; break
        if ok:
            hits.append((kind,D,const))
    return hits

# =====================================================================
# LENS 2: farfalle-bridge — compute the ACTUAL period of the mask-roll
#   under the proposal's σ definition, for BOTH plausible interpretations,
#   AND check whether untouched lanes create a fixed subspace / short cycle.
# =====================================================================
def mask_roll_full_period(n,red,sigma,w,P,start=None):
    """roll = σ-then-π applied to the full w-lane mask. Find exact period
    by Floyd-free direct iteration up to the group bound. The mask space is
    (2^n)^w which is large; instead we exploit that the map is linear over
    each lane's GF, so period = lcm over orbit. We just iterate from a random
    nonzero start until we return to it OR detect a non-injective collapse."""
    al=alpha_factory(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def roll(mask):
        y=list(mask)
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    M=(1<<n)-1
    if start is None:
        random.seed(0); start=tuple(random.randint(1,M) for _ in range(w))
    seen={}; cur=start; t=0; cap=(1<<n)*w*8+10
    while t<cap:
        if cur in seen: return ("cycle", t-seen[cur], seen[cur])
        seen[cur]=t; cur=roll(cur); t+=1
    return ("no-cycle", cap, None)

def mask_roll_is_injective(n,red,sigma,w,P):
    """Is roll a permutation of the mask space? If an untouched lane is just
    permuted by π it's fine; but if two distinct masks roll to the same mask,
    the mask schedule repeats -> Farfalle key/mask collision."""
    al=alpha_factory(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def roll(mask):
        y=list(mask)
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    # injectivity over full space is too big for n=8,w=8; test per-lane structure:
    # each output lane = alpha^{k or 0}( input lane P[i] ). alpha^k is a bijection,
    # identity is a bijection, pi is a permutation => roll is a bijection composition.
    # So injectivity is structural. But FIXED POINTS / short cycles matter -> handled by period.
    # Here we directly verify bijection on a small instance.
    if n*w>20: return "structural-bijection (alpha^k and id both bijective, pi perm)"
    seen=set(); tot=1<<(n*w)
    for code in range(tot):
        mask=tuple((code>>(i*n))&((1<<n)-1) for i in range(w))
        seen.add(roll(mask))
    return ("inj" if len(seen)==tot else "NOT-inj", len(seen), tot)

if __name__=="__main__":
    random.seed(12345)
    PI=[7,4,1,6,3,0,5,2]
    SIG_minimal=[(0,1),(4,3)]              # proposal minimal σ{0,4}
    SIG_full=[(i,i+1) for i in range(8)]   # proposal full-lane σ k=1..8
    eps=[1,-1,1,-1,1,-1,1,-1]

    print("################ LENS: prob1-subspace ################")
    for R in [1,2,3]:
        print(f"-- n=8,w=8, R={R}, σ minimal{{0,4}} --")
        hits=find_prob1_inactive_multiround(8,8,3,4,eps,SIG_minimal,0x1D,PI,R,samples=2000)
        nz=[h for h in hits]
        print(f"   prob-1 inactive/iterative differentials found: {len(nz)}")
        for kind,D,const in nz[:8]:
            print(f"     kind={kind} D={['%x'%d for d in D]} -> const out-diff const_nonzero={any(const)}")
    print()
    print("################ LENS: farfalle-bridge ################")
    print("-- mask-roll period (σ-then-π on full mask), MINIMAL σ{0,4}=α^1,α^3 --")
    for n,red in [(4,0x3),(5,0x5),(6,0x1B),(8,0x1D)]:
        r=mask_roll_full_period(n,red,SIG_minimal,8,PI)
        print(f"   n={n} red={hex(red)}: {r}  (full-LFSR period would be {2**n-1})")
    print("-- mask-roll period, FULL σ k=1..8 --")
    for n,red in [(4,0x3),(5,0x5),(6,0x1B),(8,0x1D)]:
        r=mask_roll_full_period(n,red,SIG_full,8,PI)
        print(f"   n={n} red={hex(red)}: {r}  (full-LFSR period would be {2**n-1})")
    print("-- roll injectivity (small) --")
    for n,red in [(2,0x3),]:
        print(f"   n={n}: {mask_roll_is_injective(n,red,SIG_minimal,8,PI)}")
