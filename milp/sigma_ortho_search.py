#!/usr/bin/env python3
"""
⊟-orthomorphism (additive Lai-Massey) 탐색 — ARX/no-S-box 후보 전수(n=8,16).
'orthomorphism w.r.t. ⊟' 가 핵심: zero-sum reduction이 ⊞ 기반이므로 보존되는
Lai-Massey 불변이 ⊟-차분 세계에 산다. σ가 ⊟-orthomorphism이어야 그 불변을 죽인다.

조건:
  (P)  σ perm
  (O⊟) x ↦ σ(x) ⊟ x perm    (← 가산 Lai-Massey가 요구하는 진짜 ortho)
  (O⊕) x ↦ σ(x) ⊕ x perm    (보너스: XOR 차분도 죽이면 더 강함)

후보군: ARX 1-2연산 합성 (xor-rot, add-const, sub, mixed). no-S-box.
"""
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    return m,rotl

def is_perm(f,n):
    seen=bytearray(1<<n)
    for x in range(1<<n):
        y=f(x)&((1<<n)-1)
        if seen[y]: return False
        seen[y]=1
    return True

def classify(name,f,n,out):
    P=is_perm(f,n)
    if not P:
        return
    m=(1<<n)-1
    Osub=is_perm(lambda x:(f(x)-x)&m,n)
    Oxor=is_perm(lambda x:(f(x)^x)&m,n)
    if Osub or Oxor:
        out.append((name,P,Osub,Oxor))

def search(n):
    m,rotl=mk(n)
    out=[]
    # family 1: θ(x) = (x ⊕ ROTL(x,r)) ⊞ c
    for r in range(1,n):
        for c in (1,3):
            classify(f"(x⊕ROTL{r})⊞{c}", (lambda r,c:(lambda x:((x^rotl(x,r))+c)&m))(r,c), n, out)
    # family 2: θ(x) = (x ⊞ c) ⊕ ROTL(x,r)   (nonlinear due to carry-before-xor)
    for r in range(1,n):
        for c in (1,3):
            classify(f"(x⊞{c})⊕ROTL{r}", (lambda r,c:(lambda x:((x+c)&m)^rotl(x,r)))(r,c), n, out)
    # family 3: θ(x) = ROTL(x⊞c, r) ⊕ x
    for r in range(1,n):
        for c in (1,3):
            classify(f"ROTL(x⊞{c},{r})⊕x", (lambda r,c:(lambda x:rotl((x+c)&m,r)^x))(r,c), n, out)
    # family 4: θ(x)= x ⊞ (ROTL(x,r) ⊕ ROTL(x,s))   (two-rot xor then add)
    for r in range(1,n):
        for s in range(r+1,n):
            classify(f"x⊞(ROTL{r}⊕ROTL{s})", (lambda r,s:(lambda x:(x+(rotl(x,r)^rotl(x,s)))&m))(r,s), n, out)
    # family 5: θ(x)= (ROTL(x,r) ⊞ x) ⊕ c   const-xor after add-rot (perm? add-rot not perm... skip)
    # family 6: θ(x)= x ⊕ ((x ⊞ c) ⋙? )  -- emulate alpha-like via add+xor
    # family 7: GF alpha-mult then xor-const
    def alpha(red):
        def a(v):
            return (((v<<1)&m) ^ (red if (v>>(n-1)) else 0))
        return a
    reds={8:[0x1D,0x1B,0x2D],16:[0x2B,0x2D,0x1B]}.get(n,[])
    for red in reds:
        a=alpha(red)
        classify(f"alpha(red=0x{red:X})", a, n, out)
        # alpha then add-const (try to get ⊟-ortho)
        for c in (1,3):
            classify(f"alpha(0x{red:X})⊞{c}", (lambda a,c:(lambda x:(a(x)+c)&m))(a,c), n, out)
        # alpha then sub-const
        classify(f"alpha(0x{red:X})⊟1", (lambda a:(lambda x:(a(x)-1)&m))(a), n, out)
    print(f"== ⊟/⊕-orthomorphism hits, n={n} ==")
    if not out:
        print("  (none in tested families)")
    for name,P,Osub,Oxor in out:
        tag = "FULL(⊟&⊕)" if (Osub and Oxor) else ("⊟-ortho" if Osub else "⊕-ortho")
        print(f"  {name:28s} perm={P} ⊟={Osub} ⊕={Oxor}   [{tag}]")
    print()
    return out

if __name__=="__main__":
    search(8)
    search(16)
