#!/usr/bin/env python3
"""
Adversarial lens: farfalle-bridge.

Proposal C4 claim: sigma = GF alpha-mult on lanes {0,2,4,6} with k={1,3,5,7} serves as the
Farfalle mask-roll, period 2^32-1, non-repeating, and is an orthomorphism. I check:

 (1) mask-roll PERIOD: in ypsilenti the roll was roll(mask)=alpha*mask applied to the WHOLE
     mask (all lanes), giving LFSR period 2^32-1 per lane. But the proposal's sigma only
     touches 4 of 8 lanes, and k differs per lane (1,3,5,7). What is the actual roll map and
     its period if used as the mask-roll? CRITICAL: lanes 1,3,5,7 get NO alpha-mult at all.
     If the "roll" = one round (incl pi), what is the period / does any lane stay constant?

 (2) Is sigma an orthomorphism? proposal admits it is a XOR-orthomorphism (x -> a^k(x) ^ x is
     a perm) but NOT a sub-orthomorphism. For Lai-Massey linear security you need x->sigma(x)-x
     OR x->sigma(x)^x to be a perm (orthomorphism). Verify XOR-orthomorphism for k=1,3,5,7.

 (3) THE KEY FARFALLE QUESTION: a Farfalle mask-roll must produce DISTINCT masks for distinct
     roll counts (mask injectivity / no short cycles / no fixed points other than 0). If roll
     only multiplies SOME lanes by alpha^k and leaves others fixed, then lanes that are never
     multiplied NEVER change -> mask roll has a HUGE fixed subspace -> repeated masks for inputs
     differing only in untouched lanes. Check.

 (4) But actually the proposal says roll(mask)=alpha*mask 'lane별 alpha^k' meaning EACH lane k
     gets its own alpha power as the roll. Re-read: "mask-roll: roll(mask)=α·mask (lane별 α^k)".
     This is ambiguous. Test BOTH interpretations.
"""
def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1))&1 else 0))
    return a

def order_of_alpha(n,red):
    a=make_alpha(n,red)
    # multiplicative order of alpha (=x) in GF(2^n)*
    x=1; cnt=0
    while True:
        x=a(x); cnt+=1
        if x==1: return cnt
        if cnt>(1<<n)+2: return None

def xor_orthomorphism(n,red,k):
    a=make_alpha(n,red)
    def apow(x):
        for _ in range(k): x=a(x)
        return x
    img={apow(x)^x for x in range(1<<n)}
    return len(img)==(1<<n)

def sub_orthomorphism(n,red,k):
    a=make_alpha(n,red)
    def apow(x):
        for _ in range(k): x=a(x)
        return x
    img={(apow(x)-x)&((1<<n)-1) for x in range(1<<n)}
    return len(img)==(1<<n)

def mask_roll_period_interp_A(n,red,sigma,w,P,rolls_max=None):
    """Interpretation A: roll = ONE application of the sigma layer (alpha^k on lanes in sigma)
       followed by pi (since roll in Farfalle is the actual round-derived map). But masks roll
       WITHOUT the nonlinear part typically. Here test the simplest: roll = sigma o pi on the
       full w-lane mask. Period = smallest t>0 s.t. (sigma o pi)^t = identity on all masks?
       We test on a random nonzero mask and also check fixed lanes."""
    a=make_alpha(n,red)
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    def roll(mask):
        y=list(mask)
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    # which lanes ever get multiplied across the pi cycle?
    touched=set(ln for ln,_ in sigma)
    # period on a generic mask
    import random
    random.seed(0)
    M=(1<<n)-1
    mask=tuple(random.randint(1,M) for _ in range(w))
    seen={}; cur=mask; t=0
    cap=(rolls_max or ((1<<n)*4))
    while t<cap:
        if cur in seen:
            return ("cycle", t-seen[cur], seen[cur], touched)
        seen[cur]=t; cur=roll(cur); t+=1
    return ("no-cycle-within-cap", cap, None, touched)

def mask_roll_period_interp_B(n,red):
    """Interpretation B: roll(mask) = alpha * mask on EVERY lane (classic LFSR). period = ord(alpha)."""
    return order_of_alpha(n,red)

if __name__=="__main__":
    SIG=[(0,1),(2,3),(4,5),(6,7)]
    PPI=[7,4,1,6,3,0,5,2]
    print("=== (2) sigma orthomorphism check (k=1,3,5,7) ===")
    for n,red in [(8,0x1D),(16,0x2B)]:
        print(f"  n={n} red={hex(red)}: ord(alpha)={order_of_alpha(n,red)} (=2^{n}-1? {order_of_alpha(n,red)==(1<<n)-1})")
        for k in [1,3,5,7]:
            print(f"    k={k}: XOR-ortho={xor_orthomorphism(n,red,k)}  SUB-ortho={sub_orthomorphism(n,red,k)}")

    print("\n=== (1)/(3) mask-roll period, interpretation A (sigma o pi on full mask) ===")
    for n,red in [(4,0x3),(5,0x5),(6,0x1B),(8,0x1D)]:
        r=mask_roll_period_interp_A(n,red,SIG,8,PPI)
        print(f"  n={n} red={hex(red)}: {r[0]} period/preperiod={r[1]}/{r[2]} touched_lanes={sorted(r[3])} (untouched={sorted(set(range(8))-r[3])})")

    print("\n=== (4) interpretation B: roll=alpha*mask on every lane, period=ord(alpha) ===")
    for n,red in [(8,0x1D),(16,0x2B)]:
        print(f"  n={n} red={hex(red)}: period={mask_roll_period_interp_B(n,red)} (full LFSR={2**n-1})")

    # KEY: does the proposal's pi=[7,4,1,6,3,0,5,2] preserve the set {0,2,4,6} (the sigma lanes)?
    # If pi maps a touched lane into an untouched position, the alpha^k accumulation pattern
    # across rounds is scrambled. Check the orbit structure.
    print("\n=== pi orbit / sigma-lane preservation ===")
    print(f"  pi = {PPI}")
    sig_lanes={0,2,4,6}
    print(f"  sigma lanes = {sorted(sig_lanes)}")
    print(f"  pi(sigma lanes positions): new[i]=y[P[i]]; which output positions read from sigma'd lanes?")
    # after sigma, lane ln holds alpha^k(y_ln). pi puts y[P[i]] at position i.
    # output pos i is 'multiplied' if P[i] in sig_lanes
    mult_out=[i for i in range(8) if PPI[i] in sig_lanes]
    print(f"  output positions receiving an alpha-multiplied lane: {mult_out}")
    # iterate pi to see if the multiplied-set is stable
    cur=list(sig_lanes)
    for r in range(1,9):
        # track where sigma-lanes go under pi^r (as positions): a lane at pos p moves to pos i where P[i]=p
        Pinv=[0]*8
        for i in range(8): Pinv[PPI[i]]=i
        cur=[Pinv[p] for p in cur]
        print(f"    after pi^{r}: sigma-content at positions {sorted(cur)}")
