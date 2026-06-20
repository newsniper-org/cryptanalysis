#!/usr/bin/env python3
"""
INDEPENDENT prob-1 inactive subspace computation for yttrium-LM (real params).

The author's model (yttrium_lm_la.py) asserts: a difference passes the ADD-broadcast
(combiner v_i = x'_i + t) with probability 1 ONLY in the MSB bit (add==xor at MSB,
no carry out). For F to be inactive we ALSO need ΔS=0. The author encodes:
  (a) non-MSB bits of Lin^r(v) must be 0
  (b) MSB XOR-parity of Lin^r(v) must be 0 (so ΔS=0 at MSB level)

I recompute this independently with my own rank code, AND I additionally STRESS-TEST
the model's central lemma empirically at n=8,12,16 widths (a!=b real-ish):
  Lemma: the ONLY XOR-diffs Δ_i that pass  x -> x+t  with the SAME output xor-diff
         for ALL t-independent inputs are those supported on MSB.
That lemma underlies the whole R* claim. If it's false (some non-MSB diff is prob-1
inactive), then R* could be larger.
"""
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def alpha_fac(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a
def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for bb in basis: cur=min(cur,cur^bb)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def lin_factory(n,w,red,sigma,P,a,b):
    m=(1<<n)-1; al=alpha_fac(n,red)
    _,rotl,rotr=mk(n)
    def apw(v,k):
        for _ in range(k): v=al(v)
        return v
    def words(s): return [(s>>(i*n))&m for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&m)<<(i*n)
        return s
    def Lin(s):
        ws=words(s)
        ws=[rotl(x,a) for x in ws]
        ws=[rotr(x,b) for x in ws]
        for (lane,k) in sigma: ws[lane]=apw(ws[lane],k)
        return pack([ws[P[i]] for i in range(w)])
    return Lin,words,m

def inactive_dim(n,w,red,sigma,P,a,b,R):
    Lin,words,m=lin_factory(n,w,red,sigma,P,a,b)
    N=n*w; cols=[]
    for k in range(N):
        cur=1<<k; col=0; bp=0
        for r in range(R):
            ws=words(cur)
            for x in ws:
                col|=(x&(m^(1<<(n-1))))<<bp; bp+=n   # non-MSB must be 0
            mx=0
            for x in ws: mx^=(x>>(n-1))&1            # MSB parity must be 0
            col|=mx<<bp; bp+=1
            cur=Lin(cur)
        cols.append(col)
    return N-gf2_rank(cols)

def empirical_add_pass_lemma(n,red):
    """Empirically: which XOR-diffs Δ on a single word satisfy
       (x+t)^((x^Δ)+t) == Δ  for ALL x,t  (prob-1 pass through ADD-broadcast)?
       Should be ONLY Δ in {0, 2^(n-1)} per author's MSB lemma."""
    m=(1<<n)-1
    passers=[]
    for d in range(1,1<<n):
        ok=True
        for x in range(1<<n):
            for t in range(1<<n):
                if ((x+t)&m)^(((x^d)+t)&m)!=d:
                    ok=False; break
            if not ok: break
        if ok: passers.append(d)
    return passers

if __name__=="__main__":
    PI=[7,4,1,6,3,0,5,2]
    print("=== INDEPENDENT prob-1 inactive subspace (my own rank code) ===")
    for (sig,lab) in [([(0,1),(4,3)],"sig{0,4}"),
                      ([(i,i+1) for i in range(8)],"ALLsig 1..8")]:
        print(f"-- yttrium-LM n=32 (a,b)=(8,9) {lab} --")
        for R in range(1,5):
            d=inactive_dim(32,8,0x400007,sig,PI,8,9,R)
            print(f"   R={R}: dim={d}"+("  <- R*" if d==0 else ""))
            if d==0: break
    print()
    print("=== central LEMMA stress-test: prob-1 ADD-broadcast passers (single word) ===")
    for n in (3,4,5,6,7,8,9,10,11,12):
        red={3:0x3,4:0x3,5:0x5,6:0x27,7:0x9,8:0x1D,9:0x1B,10:0x207,11:0x5,12:0x807}[n]
        ps=empirical_add_pass_lemma(n,red)
        expected=[1<<(n-1)]
        ok = (ps==expected)
        print(f"   n={n}: prob-1 passers={[hex(x) for x in ps]}  expected MSB-only {hex(1<<(n-1))}  {'OK' if ok else 'VIOLATION'}")
