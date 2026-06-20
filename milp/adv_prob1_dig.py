#!/usr/bin/env python3
"""Dig into the surviving R=2 prob-1 differential 0x4040 (n4w4, a=b=1).
Is it (a) a genuine prob-1 inactive class the MSB-only LA model misses, or
(b) an artifact of degenerate a=b=1 rotation? Test across rotations and
check whether F is actually inactive (ΔS=0 every round) or whether it's a
prob-1 differential through ACTIVE F (carry/F cancellation)."""
import itertools
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def make_F(n,pairs):
    m,rotl,_=mk(n)
    pp=[(a%n,b%n) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F
def alpha_fac(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a
def make_round_traced(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs):
    m,rotl,rotr=mk(n); F=make_F(n,pairs); al=alpha_fac(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def rnd(state):
        ws=list(state)
        xp=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*xp[i])%(1<<n)
        t=F(S)
        v=[(xp[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (lane,k) in sigma_lanes: y[lane]=apow(y[lane],k)
        return tuple(y[P[i]] for i in range(w)), S
    return rnd

def check_diff(n,w,a,b,eps,sig,red,P,pairs,d,R):
    m=(1<<n)-1
    rnd=make_round_traced(n,w,a,b,eps,sig,red,P,pairs)
    dw=tuple((d>>(i*n))&m for i in range(w))
    outdiffs=set(); deltaS_active=0; total=0
    for code in range(1<<(n*w)):
        st=tuple((code>>(i*n))&m for i in range(w))
        st2=tuple(st[i]^dw[i] for i in range(w))
        a1=st; a2=st2; ods=[]
        Sdiff_zero_all=True
        for r in range(R):
            a1,S1=rnd(a1); a2,S2=rnd(a2)
            if S1!=S2: Sdiff_zero_all=False
        od=tuple(a1[i]^a2[i] for i in range(w))
        outdiffs.add(od); total+=1
        if not Sdiff_zero_all: deltaS_active+=1
        if len(outdiffs)>1:
            # not prob-1; still report
            pass
    return len(outdiffs), deltaS_active, total

if __name__=="__main__":
    PAIRS=[(7,17),(3,21),(9,29)]
    print("Investigate 0x4040 in n4w4 a=b=1, sig (0,1),(2,3), red=0x3, P=[3,0,1,2]")
    nd,act,tot=check_diff(4,4,1,1,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],PAIRS,0x4040,2)
    print(f"  R=2: #outdiffs={nd}  (1 => prob-1)   ΔS!=0 in {act}/{tot} inputs")
    print(f"  => F {'ALWAYS inactive (ΔS=0) — a TRUE prob-1 inactive class the MSB model missed' if act==0 else 'sometimes active but diff still prob-1 (F-cancellation)' if nd==1 else 'not prob-1'}")
    print()
    # bit layout of 0x4040 in n=4: word values
    d=0x4040
    print("  word values:", [(d>>(i*4))&0xf for i in range(4)], "(bit2 set on lanes 1,3; MSB is bit3)")
    print()
    # Is it artifact of a=b=1? sweep rotations on n4w4
    print("Sweep rotations (n4w4) — does an R=2 prob-1 inactive survivor exist for non-degenerate (a,b)?")
    import itertools as it
    for a in range(0,4):
        for b in range(0,4):
            m=(1<<4)-1
            rnd=make_round_traced(4,4,a,b,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],PAIRS)
            def rndR(st,R):
                for _ in range(R): st,_=rnd(st)
                return st
            cands=set()
            for i in range(4):
                for bit in range(4): cands.add((1<<bit)<<(i*4))
            for r in range(1,5):
                for combo in it.combinations(range(4),r):
                    for bit in range(4):
                        dd=0
                        for i in combo: dd|=(1<<bit)<<(i*4)
                        cands.add(dd)
            cands.discard(0)
            surv=[]
            for dd in cands:
                dw=tuple((dd>>(i*4))&m for i in range(4))
                ods=set()
                for code in range(1<<16):
                    st=tuple((code>>(i*4))&m for i in range(4))
                    st2=tuple(st[i]^dw[i] for i in range(4))
                    x=rndR(st,2); y=rndR(st2,2)
                    ods.add(tuple(x[i]^y[i] for i in range(4)))
                    if len(ods)>1: break
                if len(ods)==1: surv.append(dd)
            tag = "  <-- SURVIVOR(S) at R=2" if surv else ""
            print(f"  a={a} b={b}: R=2 prob-1 survivors={len(surv)} {','.join(hex(x) for x in surv[:5])}{tag}")
