# Farfalle mask-roll: the proposal JSON's bridge claim is that GF alpha-mult IS the mask-roll
# (period 2^n-1 primitive LFSR). The actual mask-roll in ypsilenti was a per-lane alpha-mult.
# Check: if roll = per-lane alpha^{c} (single power c on EVERY lane) the period is ord(alpha).
# We already confirmed ord(alpha)=2^32-1 at n=32 (primitive). So the *intended* mask-roll
# (alpha on every lane) is fine. The QUESTION is whether the ROUND'S sigma (subset of lanes,
# distinct powers) is what's used as the roll. The proposal says mask-roll = alpha-roll of the
# key/mask (NOT the round). So mask-roll injectivity reduces to: is alpha-mult a permutation
# with full period? YES at n=32. Confirm there's no fixed nonzero point and distinct counts
# give distinct masks for a single-lane LFSR mask.
def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1))&1 else 0))
    return a

for n,red in [(8,0x1D),(16,0x2B),(16,0x1002D)]:
    a=make_alpha(n,red)
    # fixed points of alpha: a(x)=x
    fp=[x for x in range(1<<n) if a(x)==x]
    # order
    x=1;c=0
    while True:
        x=a(x);c+=1
        if x==1 or c>(1<<n): break
    print(f"n={n} red={hex(red)}: ord(alpha)={c} full={c==(1<<n)-1}  fixedpoints(alpha)={fp}")

# n=32 fixed point + period already confirmed primitive. Show single-lane roll injectivity:
# masks m, alpha*m, alpha^2*m ... are all distinct for 2^32-1 steps (since primitive, orbit of any
# nonzero m has length 2^32-1). Only fixed point is 0. This is the LFSR guarantee.
print("n=32 red=0x400007: primitive (confirmed earlier) => orbit of any nonzero mask length 2^32-1, only fixed point=0 (mask must be nonzero).")

# Also: encode/path injectivity concern -- if path encoding collides, masks collide. That's a
# Farfalle spec detail unchanged by this redesign (proposal says leaf/internal/mask derivation
# unmodified). So bridge change is localized to reduction; mask-roll algebra intact.
