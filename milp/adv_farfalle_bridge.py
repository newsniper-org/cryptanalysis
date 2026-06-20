#!/usr/bin/env python3
"""
ADVERSARIAL farfalle-bridge checks for yttrium-LM sigma (GF alpha-mult).
Claims to break:
  (B1) red 0x400007 primitive over GF(2^32) => alpha order = 2^32-1 (no short cycle / repeated mask).
  (B2) sigma = alpha-mult is a permutation (perm).
  (B3) sigma ^ id is a permutation (XOR-orthomorphism) -> Lai-Massey valid.
  (B4) sigma - id (mod 2^n) is NOT a permutation (additive orthomorphism fails) -> consistent with their reasoning.
  (B5) per-lane distinct powers k_i: do alpha^{k_i} ever coincide (mask repeat across lanes)? only if k_i==k_j mod ord.
  (B6) encode/mask injectivity: alpha-roll k_path = alpha^path applied -> distinct paths distinct masks iff path < ord.
"""
def alpha_step(v,n,red):
    m=(1<<n)-1
    return (((v<<1)&m)^(red if (v>>(n-1)) else 0))

def order_of_alpha(n,red,cap=None):
    """multiplicative order of x in GF(2^n)/<red>. Start from 1, multiply by alpha."""
    m=(1<<n)-1
    v=1; cnt=0
    target=(1<<n)-1
    if cap is None: cap=target+5
    seen_one=False
    v=alpha_step(1,n,red)  # = x
    cnt=1
    while cnt<=cap:
        if v==1:
            return cnt
        v=alpha_step(v,n,red); cnt+=1
    return None

def is_perm_small(f,n):
    m=(1<<n)-1
    seen=set()
    for x in range(1<<n):
        seen.add(f(x))
    return len(seen)==(1<<n)

# --- fast GF(2^n) multiply and pow for primitivity test ---
def gf_mul(a,b,n,poly):
    """poly = full reduction polynomial WITHOUT the x^n term, i.e. low n bits (the 'red').
       alpha_step(v)=v<<1 ^ red if msb. So modulus = x^n + red(x)."""
    m=(1<<n)-1
    res=0
    while b:
        if b&1: res^=a
        b>>=1
        msb=a>>(n-1)
        a=((a<<1)&m)^(poly if msb else 0)
    return res
def gf_pow(a,e,n,poly):
    r=1
    while e:
        if e&1: r=gf_mul(r,a,n,poly)
        a=gf_mul(a,a,n,poly)
        e>>=1
    return r
def is_primitive_alpha(n,poly):
    """alpha = x (value 2). primitive iff order = 2^n-1.
       Check alpha^(2^n-1)=1 and alpha^((2^n-1)/p)!=1 for each prime p | 2^n-1."""
    order=(1<<n)-1
    alpha=2
    if gf_pow(alpha,order,n,poly)!=1:
        return False, "alpha^(2^n-1) != 1 (poly not even irreducible-consistent)"
    # factor order
    facs=factorize(order)
    for p in facs:
        if gf_pow(alpha,order//p,n,poly)==1:
            return False, f"alpha^((2^n-1)/{p})==1 => order proper divisor (NOT primitive)"
    return True, f"primitive; prime factors of 2^n-1 = {sorted(facs)}"
def factorize(x):
    fs=set(); d=2
    while d*d<=x:
        while x%d==0: fs.add(d); x//=d
        d+=1
    if x>1: fs.add(x)
    return fs

if __name__=="__main__":
    print("=== (B1) primitivity of alpha=x (fast GF(2^n) pow test) ===")
    for (n,red) in [(4,0x3),(5,0x5),(6,0x27),(8,0x1D),(8,0x2D),(8,0x1B),(16,0x2B)]:
        ok,why=is_primitive_alpha(n,red)
        print(f"  n={n} red={hex(red)}: primitive={ok}  ({why})")
    ok,why=is_primitive_alpha(32,0x400007)
    print(f"  n=32 red=0x400007: primitive={ok}  ({why})")
    print()
    print("=== (B2)-(B4) orthomorphism properties (small n exhaustive) ===")
    for (n,red) in [(4,0x3),(6,0x27),(8,0x1D),(8,0x2D),(8,0x1B),(10,0x207),(12,0x807),(16,0x2B)]:
        m=(1<<n)-1
        f=lambda x: alpha_step(x,n,red)
        perm=is_perm_small(f,n)
        xor_orth=is_perm_small(lambda x: f(x)^x, n)
        add_orth=is_perm_small(lambda x: (f(x)-x)&m, n)
        print(f"  n={n} red={hex(red)}: perm={perm}  sigma^id perm(XOR-orth)={xor_orth}  sigma-id perm(ADD-orth)={add_orth}")
    print()
    print("=== (B5) per-lane distinct powers: alpha^k coincidence ===")
    # k=1..8; alpha^ki == alpha^kj iff ki==kj (mod ord). ord huge => never for k in 1..8.
    # but XOR-orthomorphism must hold for EACH power alpha^k, not just alpha^1!
    print("  Each lane uses alpha^{k}. Lai-Massey needs alpha^k ^ id to be a PERMUTATION for each k used.")
    for (n,red) in [(8,0x1D),(8,0x2D),(12,0x807),(16,0x2B)]:
        m=(1<<n)-1
        bad=[]
        for k in range(1,9):
            def fk(x,k=k):
                for _ in range(k): x=alpha_step(x,n,red)
                return x
            xo=is_perm_small(lambda x: fk(x)^x, n)
            if not xo: bad.append(k)
        print(f"  n={n} red={hex(red)}: powers k=1..8 with XOR-orth FAIL: {bad if bad else 'none (all OK)'}")
