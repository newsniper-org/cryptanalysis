#!/usr/bin/env python3
"""
The deepest test: ADDITIVE Lai-Massey invariant survival under XOR-ortho sigma.

Classical Lai-Massey invariant: the reduction reads off a combination C(state) and
the round preserves C up to the orthomorphism. For the SIGNED-SUM additive reduction
  S = sum_i eps_i * ROTL_a(x_i)   (mod 2^n),  sum eps = 0
the proposal's invertibility relies on:  sum_i eps_i * v_i = S  (v_i = u_i ⊞ t).
That SAME identity means S is an INVARIANT combination that passes through the combiner
unchanged. The orthomorphism sigma + pi must scramble it so it does not survive as a
probability-1 / iterative distinguisher.

Concretely, define the "Lai-Massey functional" L(state)=S (signed sum of ROTL_a lanes).
After one full round, the new state's S' = signed-sum of ROTL_a(new lanes). Question:
is there a NONZERO input difference D such that ΔL = 0 with probability 1 across rounds,
i.e. the signed-sum is differentially inactive for many rounds?

This generalizes the MSB-only model in yttrium_lm_la.py. The repo model ASSUMES the only
prob-1 inactive diffs are MSB-pairs. We test additive differences D with sum eps_i*ROTL_a(D_i)=0
(mod 2^n) that are NOT MSB-based, and see if they pass prob-1 through the combiner.

Also: test the SUB-orthomorphism gap concretely — find collisions in x ⊟ sigma(x) and
see if they create an iterative additive invariant the round fails to kill.
"""
import random, itertools

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
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
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
    def rnd(state):
        ws=list(state)
        u=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (ln,k) in sigma_lanes: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    def Lfun(state):  # signed-sum reduction functional
        u=[rotl(state[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        return S
    return rnd,Lfun,m

def hunt_prob1_signedsum_inactive(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,R,samples=3000):
    """Search additive input differences D (low weight) for prob-1 R-round
    output additive difference (full state) OR prob-1 inactivity of S across R rounds."""
    rnd,Lfun,m=make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P)
    def Rrnd_trace_S(x):
        Ss=[]
        for r in range(R):
            Ss.append(Lfun(x)); x=rnd(x)
        return x,Ss
    cands=[]
    # additive single-lane diffs of every bit position
    for ln in range(w):
        for bit in range(n):
            D=[0]*w; D[ln]=1<<bit; cands.append(tuple(D))
    # signed-sum-zero additive diffs on lane pairs with equal value (eps_i+eps_j may cancel)
    for (i,j) in itertools.combinations(range(w),2):
        for bit in range(n):
            D=[0]*w; D[i]=1<<bit; D[j]=1<<bit; cands.append(tuple(D))
    found_outconst=[]; found_Sinactive=[]
    for D in cands:
        if all(d==0 for d in D): continue
        outconst=None; ok_out=True
        Sdiff_const=None; ok_S=True
        for _ in range(samples):
            x=tuple(random.randint(0,m) for _ in range(w))
            x2=tuple((x[i]+D[i])&m for i in range(w))
            o1,S1=Rrnd_trace_S(x); o2,S2=Rrnd_trace_S(x2)
            od=tuple((o1[i]-o2[i])&m for i in range(w))
            if outconst is None: outconst=od
            elif od!=outconst: ok_out=False
            Sd=tuple((S1[r]-S2[r])&m for r in range(R))
            if Sdiff_const is None: Sdiff_const=Sd
            elif Sd!=Sdiff_const: ok_S=False
            if not ok_out and not ok_S: break
        if ok_out: found_outconst.append((D,outconst))
        if ok_S and any(s==0 for s in Sdiff_const):
            # S inactive in at least one round prob-1
            allzero = all(s==0 for s in Sdiff_const)
            found_Sinactive.append((D,Sdiff_const,allzero))
    return found_outconst, found_Sinactive

if __name__=="__main__":
    random.seed(2024)
    PI=[7,4,1,6,3,0,5,2]
    eps=[1,-1,1,-1,1,-1,1,-1]
    print("##### prob-1 signed-sum-inactive / output-const hunt (n=8,w=8) #####")
    for sig_name,SIG in [("minimal{0,4}",[(0,1),(4,3)]),
                         ("full k=1..8",[(i,i+1) for i in range(8)])]:
        for R in [1,2,3]:
            oc,si=hunt_prob1_signedsum_inactive(8,8,3,4,eps,SIG,0x1D,PI,R,samples=1500)
            print(f"  sig={sig_name} R={R}: prob1-output-const diffs={len(oc)}  "
                  f"S-inactive(>=1 round prob1)={len(si)}")
            for D,sd,allz in si[:5]:
                print(f"      S-inactive D={['%x'%d for d in D]} Sdiff_per_round={['%x'%s for s in sd]} all_rounds_inactive={allz}")

    print("\n##### n=16 sanity (a,b)=(5,6) #####")
    for sig_name,SIG in [("minimal{0,4}",[(0,1),(4,3)])]:
        for R in [1,2]:
            oc,si=hunt_prob1_signedsum_inactive(16,8,5,6,eps,SIG,0x2B,PI,R,samples=800)
            print(f"  sig={sig_name} R={R}: prob1-output-const={len(oc)} S-inactive={len(si)}")
