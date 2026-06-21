#!/usr/bin/env python3
"""
Part 2: Berlekamp-Massey linear complexity of REAL (nonlinear) yttrium output
sequences, + reachability/controllability of the F-injection channel B, +
investigation of the R=7->8->9 observability rank defect and the identical
per-lane char polynomials.

Question being tested (the SSM headline):
  Does the GF(2)-linear backbone make any observed/iterated sequence have a
  SHORT linear complexity (predictable via LFSR / Berlekamp-Massey)?  If the
  real round's output bit, iterated t -> t+1, follows a short linear recurrence,
  that is a keystream-style predictability weakness.

We test the strongest version: feed the FULL nonlinear permute (with F, RC) and
do BM on (a) a single output bit across rounds, (b) the reduce-scalar S across
rounds, for many random starting states; compare to the linear-backbone-only
linear complexity (= min poly degree ~248).
"""
import sys, random
sys.path.insert(0, "/home/ybi/cryptanalysis/milp")
import ssm_backbone as bb

MASK32 = (1 << 32) - 1
W = 8
P_PI = [7, 4, 1, 6, 3, 0, 5, 2]
SIG_K = [1, 2, 3, 4, 5, 6, 7, 9]
EPS_PLUS = [True, False, True, False, True, False, True, False]
F_ROT = [(7, 17), (3, 21), (9, 29)]
ROT_A, ROT_B = 8, 9
SHA256_K = [
 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]
def rc(r): return SHA256_K[r] if r < 64 else SHA256_K[r % 64] ^ r

def rotl(x,k):
    k%=32; return ((x<<k)|(x>>(32-k)))&MASK32 if k else x&MASK32
def rotr(x,k): return rotl(x,(32-(k%32))%32)
def alpha(y):
    top=(y>>31)&1; return (((y<<1)&MASK32)^(bb.RED if top else 0))
def apow(y,k):
    for _ in range(k): y=alpha(y)
    return y
def F(s):
    acc=s
    for a,b in F_ROT: acc^=rotl(s,a)&rotl(s,b)
    return acc&MASK32
def reduce_S(xp):
    s=0
    for i in range(W):
        s=(s+xp[i])&MASK32 if EPS_PLUS[i] else (s-xp[i])&MASK32
    return s
def round_full(state,r):
    st=list(state)
    st[r%W]^=rc(r)
    xp=[rotl(st[i],ROT_A) for i in range(W)]
    s=reduce_S(xp); t=F(s)
    y=[apow(rotr((xp[i]+t)&MASK32,ROT_B),SIG_K[i]) for i in range(W)]
    return [y[P_PI[i]] for i in range(W)], s

# ---------- Berlekamp-Massey over GF(2) ----------
def berlekamp_massey(bits):
    n=len(bits); b=[1]+[0]*n; c=[1]+[0]*n
    L=0; m=-1; bb_=1
    for i in range(n):
        d=bits[i]
        for j in range(1,L+1):
            d^=c[j]&bits[i-j]
        if d:
            t=c[:]
            for j in range(0,n-(i-m)):
                if i-m+j<=n:
                    c[i-m+j]^=b[j]
            if 2*L<=i:
                L=i+1-L; m=i; b=t
    return L

if __name__=="__main__":
    print("== Berlekamp-Massey linear complexity of REAL nonlinear sequences ==")
    print("(linear-backbone-only min-poly degree ~248; short LC would = predictable)")
    NSEQ=300
    random.seed(7)
    for label, getter in [
        ("output bit lane0[bit0]", lambda st: st[0]&1),
        ("output bit lane3[bit17]", lambda st: (st[3]>>17)&1),
        ("reduce-scalar S bit0",    None),
    ]:
        Ls=[]
        for _ in range(20):
            st=[random.getrandbits(32) for _ in range(W)]
            bits=[]
            for r in range(NSEQ):
                st,s=round_full(st,r)
                if getter is None:
                    bits.append(s&1)
                else:
                    bits.append(getter(st))
            Ls.append(berlekamp_massey(bits))
        import statistics
        print(f"  {label:24s}: LC over {NSEQ} rounds = min {min(Ls)}, med {int(statistics.median(Ls))}, max {max(Ls)}  (ideal ~{NSEQ//2})")

    # ---- reachability/controllability of injection channel B ----
    # t is injected: y_i = ROTR9(x'_i + t).  GF(2)-linearize the +t as XOR of t into
    # every lane (carry ignored): contribution of t to next state =
    #   pi( sigma( ROTR9( broadcast(t) ) ) ).  B = that 256x32 map (image of t).
    # Reachability matrix R = [B, A B, A^2 B, ...]; unreachable = states t never affects.
    print("\n== reachability of F-injection channel B (does t reach all of state?) ==")
    A=bb.build_A_columns()
    # B: image of a t-word (32 bits). For each bit j of t, t-vector = broadcast 1<<j into all lanes,
    # then ROTR9, sigma^{k_i}, pi.  Column = resulting 256-bit state contribution.
    def B_columns():
        cols=[]
        for jb in range(32):
            tword=1<<jb
            # y_i = ROTR9(t) then sigma; but +t adds t to x'_i for ALL i, so injection to lane i = sigma(ROTR9(t))
            out=0
            base=rotr(tword,ROT_B)
            for i in range(W):
                yi=apow(base,SIG_K[i])
                # this lands in output position inv where P[inv]=i
                inv=P_PI.index(i)
                for b in range(32):
                    if (yi>>b)&1: out^=1<<(inv*32+b)
            cols.append(out)
        return cols
    def apply_cols(cols,v):
        o=0;j=0
        while v:
            if v&1:o^=cols[j]
            v>>=1;j+=1
        return o
    def gf2_rank(cols):
        basis=[]
        for v in cols:
            cur=v
            for x in basis: cur=min(cur,cur^x)
            if cur: basis.append(cur);basis.sort(reverse=True)
        return len(basis)
    Bc=B_columns()
    R=list(Bc)
    Apow=[1<<j for j in range(256)]
    prev=0
    for step in range(1,12):
        r=gf2_rank(R)
        unreach=256-r
        print(f"  after {step-1} backbone steps: rank(reach)={r:3d}  unreachable dim={unreach}")
        if unreach==0: break
        Apow=bb.mat_mul(A,Apow)
        R=R+[apply_cols(Apow,bcol) for bcol in Bc]

    # ---- investigate the per-lane char poly: are lanes truly indistinguishable? ----
    print("\n== per-lane A^8 block: is it literally the SAME matrix across lanes? ==")
    A8=bb.mat_pow(A,8)
    def lane_block(M,lane):
        return [ (M[lane*32+b]>>(lane*32))&MASK32 for b in range(32)]
    blocks=[tuple(lane_block(A8,l)) for l in range(W)]
    for l in range(1,W):
        same = blocks[l]==blocks[0]
        print(f"  lane{l} block == lane0 block: {same}")
    print("  (if all True: A^8 acts identically per lane -> sigma powers irrelevant to backbone cycle structure)")
