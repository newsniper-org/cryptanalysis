#!/usr/bin/env python3
"""
Deep dive into the Farfalle mask-roll structure under the proposal's sigma.

In Farfalle, the mask-roll roll() is iterated to produce per-input/per-block masks
(rolling key). Security requires:
  (R1) roll is a bijection on the mask space (no mask collisions across roll counts).
  (R2) roll has LONG period from the working start (the IV-derived mask) so masks
       don't repeat within the data limit.
  (R3) NO LARGE FIXED / SHORT-CYCLE SUBSPACE: if a subspace of masks is fixed (or
       short-cycled) by roll, then for IV/keys landing in that subspace the rolled
       masks repeat quickly -> forgery / key-recovery (this is the classic Farfalle
       roll requirement; alpha-LFSR avoids it by being a single primitive cycle on
       GF(2^n)\{0}).

The proposal's roll = (sigma: alpha^{k} on SOME lanes) ∘ (pi: word permutation).
Untouched lanes get NO multiplication. KEY QUESTION: does the linear map roll on the
full mask space (GF(2)^{n*w}) have eigen/fixed structure (short cycles) because some
lanes are pure permutation?

We analyze roll as a linear map over GF(2) (alpha-mult and pi are both GF(2)-linear),
compute its ORDER (= period as a linear map = lcm of invariant-factor orders), and the
dimension of its fixed space (kernel of roll - I).
"""
import itertools

def alpha_matrix(n,red):
    """GF(2) matrix of x->alpha*x on column vectors (bit0=LSB)."""
    # alpha*x: shift left by 1, if top bit set xor red.
    cols=[]
    for b in range(n):
        v=1<<b
        top=v>>(n-1)
        r=((v<<1)&((1<<n)-1))^(red if top else 0)
        cols.append(r)
    # build matrix: out_bit i depends on in basis -> store as list of n integers (each col image)
    return cols  # cols[b] = image of e_b

def apply_lane_matrix(cols,x,n):
    out=0
    for b in range(n):
        if (x>>b)&1: out^=cols[b]
    return out&((1<<n)-1)

def mat_pow_cols(cols,k,n):
    """compose alpha-matrix k times -> column images."""
    cur=list(range(n))  # identity images? no. start identity
    cur=[1<<b for b in range(n)]
    for _ in range(k):
        cur=[apply_lane_matrix(cols,c,n) for c in cur]
    return cur

def build_roll_matrix(n,w,red,sigma,P):
    """Full GF(2) matrix (n*w x n*w) of roll = pi ∘ sigma, as column images.
       state bit index = lane*n + bit."""
    N=n*w
    acols=alpha_matrix(n,red)
    # precompute alpha^k column images per needed k
    sig={ln:k for ln,k in sigma}
    powcols={}
    for ln,k in sigma:
        powcols[ln]=mat_pow_cols(acols,k,n)
    # roll: first sigma per lane, then pi: new_lane i = old_lane P[i]
    # column image of basis bit (lane L, bit b):
    cols=[]
    for L in range(w):
        for b in range(n):
            # sigma on lane L
            if L in sig:
                lane_img=powcols[L][b]   # n-bit image within lane L
            else:
                lane_img=1<<b
            # pi: lane L content moves to output position i where P[i]=L
            outpos=[i for i in range(w) if P[i]==L]
            assert len(outpos)==1
            i=outpos[0]
            col=0
            for bb in range(n):
                if (lane_img>>bb)&1:
                    col |= 1<<(i*n+bb)
            cols.append(col)
    return cols,N

def gf2_rank(cols,N):
    basis=[]
    for v in cols:
        cur=v
        for bb in basis: cur=min(cur,cur^bb)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def mat_compose(A,B,N):
    """image columns of A∘B (apply B then A). A,B are column-image lists (len N)."""
    out=[]
    for col in B:  # col = image of basis e_j under B
        # apply A to col
        r=0
        for bit in range(N):
            if (col>>bit)&1: r^=A[bit]
        out.append(r)
    return out

def identity_cols(N): return [1<<b for b in range(N)]

def roll_order_and_fixed(n,w,red,sigma,P,cap=200000):
    cols,N=build_roll_matrix(n,w,red,sigma,P)
    I=identity_cols(N)
    # fixed space dim = N - rank(roll - I)
    diff=[cols[b]^I[b] for b in range(N)]
    fixed_dim=N-gf2_rank(diff,N)
    # order of roll as linear map: smallest t>0 with roll^t = I
    cur=list(cols); t=1
    while t<=cap:
        if cur==I: break
        cur=mat_compose(cols,cur,N); t+=1
    order=t if t<=cap else None
    return N,fixed_dim,order

def cycle_lengths_from_vector(n,w,red,sigma,P,start,cap):
    """actual orbit length from a concrete start mask (additive iteration)."""
    def alpha(v): return (((v<<1)&((1<<n)-1))^(red if (v>>(n-1)) else 0))
    def apow(x,k):
        for _ in range(k): x=alpha(x)
        return x
    sig={ln:k for ln,k in sigma}
    def roll(mask):
        y=list(mask)
        for ln in sig: y[ln]=apow(y[ln],sig[ln])
        return tuple(y[P[i]] for i in range(w))
    seen={}; cur=tuple(start); t=0
    while t<cap:
        if cur in seen: return t-seen[cur], seen[cur]
        seen[cur]=t; cur=roll(cur); t+=1
    return None,None

if __name__=="__main__":
    PI=[7,4,1,6,3,0,5,2]
    SIG_min=[(0,1),(4,3)]
    SIG_full=[(i,i+1) for i in range(8)]
    # also the adv_farfalle variant {0,2,4,6}=1,3,5,7
    SIG_alt=[(0,1),(2,3),(4,5),(6,7)]

    for name,SIG in [("minimal{0,4}=a^1,a^3",SIG_min),
                     ("full k=1..8",SIG_full),
                     ("{0,2,4,6}=1,3,5,7",SIG_alt)]:
        print(f"==== sigma={name} ====")
        for n,red in [(4,0x3),(5,0x5),(6,0x1B),(8,0x1D)]:
            N,fixed_dim,order=roll_order_and_fixed(n,w:=8,red=red,sigma=SIG,P=PI,cap=400000)
            print(f"  n={n}: state {N}b  roll_linear_order={order}  FIXED_subspace_dim={fixed_dim}  (2^{fixed_dim}={1<<fixed_dim} masks fixed)")
        print()

    print("==== concrete short-cycle hunt: start masks that are ZERO on touched lanes ====")
    # If touched lanes are 0, sigma=identity on them -> roll = pure pi on whole mask.
    # pi has order = lcm of cycle lengths. pi=[7,4,1,6,3,0,5,2] is a single 8-cycle -> order 8.
    # So masks with 0 on touched lanes roll with period | 8 (TINY!). This is a SHORT cycle.
    SIG=SIG_min
    for n,red in [(8,0x1D)]:
        # touched lanes for SIG_min = {0,4}. set them 0, others arbitrary nonzero
        start=[0,0xAB,0,0xCD,0,0xEF,0,0x12]  # lanes 0,4 zero
        clen,pre=cycle_lengths_from_vector(n,8,red,SIG,PI,tuple(start),cap=100000)
        print(f"  n={n} start(touched lanes 0)={['%x'%s for s in start]}: cycle_len={clen} preperiod={pre}")
        # fully zero on touched -> roll is just pi; period should be 8
        start2=[0,1,0,2,0,3,0,4]
        clen2,_=cycle_lengths_from_vector(n,8,red,SIG,PI,tuple(start2),cap=100000)
        print(f"  n={n} another touched-zero start: cycle_len={clen2}")

    print("\n==== SHORT-ORBIT HISTOGRAM over many random + structured starts (n=8, sigma_min) ====")
    import random
    random.seed(7)
    SIG=SIG_min; n=8; red=0x1D
    hist={}
    # random masks
    for _ in range(3000):
        st=tuple(random.randint(0,255) for _ in range(8))
        c,_=cycle_lengths_from_vector(n,8,red,SIG,PI,st,cap=5000)
        hist[c]=hist.get(c,0)+1
    # structured: zero on touched lanes {0,4}
    zero_touched=0; shortcount=0
    for _ in range(2000):
        st=list(random.randint(0,255) for _ in range(8))
        st[0]=0; st[4]=0
        c,_=cycle_lengths_from_vector(n,8,red,SIG,PI,tuple(st),cap=5000)
        hist[("touched0",c)]=hist.get(("touched0",c),0)+1
    print("  orbit-length histogram (random starts):")
    for k in sorted([h for h in hist if not isinstance(h,tuple)], key=lambda x:(x is None,x)):
        print(f"    len={k}: count={hist[k]}")
    print("  orbit-length histogram (touched lanes {0,4} forced 0):")
    for k in sorted([h for h in hist if isinstance(h,tuple)], key=lambda x:(x[1] is None,x[1])):
        print(f"    len={k[1]}: count={hist[k]}")
