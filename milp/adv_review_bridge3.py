#!/usr/bin/env python3
"""
FARFALLE-BRIDGE lens — reconcile proposal's sigma with the INHERITED ypsilenti roll.

Inherited bridge (farfalle-gen/NOTE-orthomorphism-roll-coincidence.md, §5 + C5):
    roll(k_0..k_{w-1}) = (alpha^1 k_0, alpha^2 k_1, ..., alpha^w k_{w-1})
    => EVERY lane multiplied, distinct power i+1, SAME map as the sigma layer.
    Proposal says Farfalle mask-derivation is "무수정" (UNMODIFIED) i.e. this roll stays.

Proposal's sigma layer (round_equations / orthomorphism_def):
    minimal: lanes {0,4} only, alpha^1, alpha^3
    full   : lanes 0..7, alpha^1..alpha^8

QUESTIONS:
 (B1) Is the proposal's sigma == the inherited roll? If sigma is partial-lane but the
      Farfalle roll is whole-lane, they are DIFFERENT maps -> the "same code / natural
      bridge" claim fails: sigma no longer IS the roll.
 (B2) Even granting "full sigma k=1..8" as the roll, the inherited roll uses powers
      1..w on the *mask* and is iterated as roll^i. But the proposal's sigma is composed
      INSIDE the round WITH pi every round. Is sigma-alone (no pi) a valid roll?
      Compute period of pure per-lane distinct-power alpha-mult WITHOUT pi (the genuine
      inherited roll) vs WITH pi (what the round does). They are different maps.
 (B3) The inherited security (NOTE R3 / C4): first w masks {k, roll(k),..} must be
      GF(2)-linearly independent (wide-pipe). Does the proposal's roll (whatever it is)
      preserve this? Check linear independence of the first few rolled masks.
 (B4) Orthomorphism in the ADDITIVE Lai-Massey: the inherited O2 was for XOR Lai-Massey
      (x ^ sigma(x) bijection). The proposal changed combiner to ADDITIVE (mod 2^n) and
      reduction to signed-sum. For the new structure, is the relevant orthomorphism
      condition still XOR-ortho, or does it need SUB-ortho (x - sigma(x) bijection)?
      The proposal ADMITS sub-ortho fails. Test whether the *additive* signed-sum
      reduction actually needs sub-ortho by constructing the invariant directly.
"""
import itertools, random

def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1)) else 0))
    return a

def apow_fn(n,red):
    a=make_alpha(n,red)
    def f(x,k):
        for _ in range(k): x=a(x)
        return x
    return f

# --- inherited roll: whole-mask, per-lane distinct power i+1, NO pi ---
def inherited_roll(n,red,w):
    ap=apow_fn(n,red)
    def roll(mask):
        return tuple(ap(mask[i], i+1) for i in range(w))
    return roll

def period_from(roll, start, cap):
    seen={}; cur=tuple(start); t=0
    while t<cap:
        if cur in seen: return t-seen[cur], seen[cur]
        seen[cur]=t; cur=roll(cur); t+=1
    return None,None

def gf2_indep(vectors):
    """are these n*w-bit vectors GF(2)-independent? returns rank."""
    basis=[]
    for v in vectors:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def pack(mask,n):
    s=0
    for i,x in enumerate(mask): s|=(x&((1<<n)-1))<<(i*n)
    return s

if __name__=="__main__":
    print("############ B1: is proposal sigma == inherited roll? ############")
    print("  inherited roll = per-lane alpha^(i+1) on ALL w lanes (NOTE §5/C5).")
    print("  proposal sigma minimal = lanes {0,4} only (alpha^1,alpha^3). other 6 lanes UNCHANGED.")
    print("  => As MAPS on the 8-word mask they are EQUAL iff inherited roll == sigma_minimal.")
    n,red,w=8,0x1D,8
    ap=apow_fn(n,red)
    # pick a mask, compare
    random.seed(1)
    mask=tuple(random.randint(1,255) for _ in range(8))
    roll_inherited=inherited_roll(n,red,w)(mask)
    # proposal minimal sigma:
    sig_min=[(0,1),(4,3)]
    sm=list(mask)
    for ln,k in sig_min: sm[ln]=ap(sm[ln],k)
    sm=tuple(sm)
    # proposal full sigma:
    sf=list(mask)
    for i in range(8): sf[i]=ap(sf[i],i+1)
    sf=tuple(sf)
    print(f"  mask              = {['%02x'%x for x in mask]}")
    print(f"  inherited roll    = {['%02x'%x for x in roll_inherited]}")
    print(f"  sigma_minimal     = {['%02x'%x for x in sm]}   == inherited? {sm==roll_inherited}")
    print(f"  sigma_full(k=1..8)= {['%02x'%x for x in sf]}   == inherited? {sf==roll_inherited}")
    print("  NOTE: inherited uses powers 1,2,3,4,5,6,7,8 ; proposal full uses 1..8 -> SAME if order matches.")

    print("\n############ B2: period of GENUINE inherited roll (no pi) ############")
    for n,red in [(4,0x3),(5,0x5),(6,0x1B),(8,0x1D)]:
        roll=inherited_roll(n,red,8)
        # cycle from a generic start
        st=tuple( (i*7+3)%((1<<n)) | 1 for i in range(8))
        st=tuple(x if x else 1 for x in st)
        per,pre=period_from(roll,st,cap=(1<<n)*64+50)
        # theoretical: lcm of ord(alpha^(i+1)) ; ord(alpha)=2^n-1 (primitive). ord(alpha^k)=(2^n-1)/gcd(k,2^n-1)
        import math
        o=2**n-1
        orders=[o//math.gcd(i+1,o) for i in range(8)]
        lcm=1
        for x in orders:
            lcm=lcm*x//math.gcd(lcm,x)
        print(f"  n={n}: measured period={per}  theoretical lcm(ord(alpha^k))={lcm}  per-lane orders={orders}")

    print("\n############ B3: wide-pipe — first w rolled masks GF(2)-independent? ############")
    for n,red in [(4,0x3),(8,0x1D)]:
        roll=inherited_roll(n,red,8)
        k0=tuple([1]*8)  # nonzero start
        masks=[]; cur=k0
        for _ in range(8):
            masks.append(pack(cur,n)); cur=roll(cur)
        r=gf2_indep(masks)
        print(f"  n={n}: rank of first 8 rolled masks = {r}/8  (independent? {r==8})")
        # Also the classic single-lane LFSR wide-pipe: {k, ak, a^2 k,..} indep
        a=make_alpha(n,red); v=[]; x=1
        for _ in range(n):
            v.append(x); x=a(x)
        print(f"        single-lane {{1,a,..,a^{n-1}}} rank = {gf2_indep(v)}/{n}")

    print("\n############ B4: additive Lai-Massey invariant — does signed-sum need SUB-ortho? ############")
    print("  Inherited orthomorphism req was O2: x^sigma(x) bijection (XOR Lai-Massey).")
    print("  Proposal uses signed-sum reduction S=sum eps_i ROTL_a(x_i) (ADDITIVE), eps cancel.")
    print("  The Lai-Massey invariant that orthomorphism must KILL is: a fixed-point/affine")
    print("  subspace where reduction output is unchanged AND sigma maps it to itself.")
    for n,red in [(8,0x1D),(9,0x11),(10,0x9)]:
        a=make_alpha(n,red)
        def ap1(x,k):
            for _ in range(k): x=a(x)
            return x
        for k in [1,2,3]:
            xor_img={ap1(x,k)^x for x in range(1<<n)}
            sub_img={(ap1(x,k)-x)&((1<<n)-1) for x in range(1<<n)}
            print(f"  n={n} k={k}: |x^sig(x) img|={len(xor_img)} (XOR-ortho {len(xor_img)==(1<<n)}) ; "
                  f"|x-sig(x) img|={len(sub_img)} (SUB-ortho {len(sub_img)==(1<<n)})")
