#!/usr/bin/env python3
"""
yttrium 가역화 sanity check (작은 n 전수).

목표:
  (1) ARX orthomorphism 후보 θ over Z/2^n 을 n=8,16 전수로 확인:
        - θ 가 치환(permutation)인가?
        - x ↦ θ(x) ⊟ x  가 치환인가?  (orthomorphism 정의: θ, θ-id 둘 다 perm)
        - x ↦ θ(x) ⊕ x  가 치환인가?  (complete-mapping / XOR-orthomorphism, 참고용)
  (2) 영합(signed) reduction S = Σ_i ε_i · x'_i 가 ⊞-broadcast 하에서 보존됨을
        작은 워드폭(n=4..8, w=8)으로 라운드 가역 전수/샘플 확인.

GPU/nvcc 금지. 순수 파이썬.

배경 사실(이 스크립트가 확증):
  - x ⊕ ROTL_a(x): 1+x^a 가 GF(2)[x]/(x^n-1) 에서 비가역(all-ones 가 커널) → 비치환.
  - x ⊞ ROTL_a(x): MSB 분석상 비치환.
  - x ⊕ ROTL_a ⊕ ROTL_b: 치환일 수 있으나 GF(2)-선형 → θ⊟id, θ⊕id 비치환(orthomorphism ✗).
  ⟹ 순수 *선형* ARX 로는 orthomorphism 불가. add-rotate-add 형(carry 비선형) 필요.
"""

MASK = lambda n: (1 << n) - 1

def rotl(x, k, n):
    k %= n
    return ((x << k) | (x >> (n - k))) & MASK(n)

def rotr(x, k, n):
    return rotl(x, (n - (k % n)) % n, n)

# ---- ARX orthomorphism 후보 ----------------------------------------------
def is_perm(f, n):
    seen = bytearray(1 << n)
    for x in range(1 << n):
        y = f(x, n) & MASK(n)
        if seen[y]:
            return False
        seen[y] = 1
    return True

def ortho_report(f, n):
    """returns (perm, sub_perm, xor_perm)"""
    p = is_perm(f, n)
    if not p:
        return (False, False, False)
    gs = lambda x, nn: (f(x, nn) - x) & MASK(nn)
    gx = lambda x, nn: (f(x, nn) ^ x) & MASK(nn)
    return (True, is_perm(gs, n), is_perm(gx, n))

def survey(name, f, ns=(8, 16)):
    out = []
    for n in ns:
        p, os, ox = ortho_report(f, n)
        out.append((n, p, os, ox))
        flag = "  <== ARX ORTHOMORPHISM" if (p and os) else ""
        print(f"  {name:34s} n={n:2d}: perm={int(p)}  (θ⊟id perm)={int(os)}  (θ⊕id perm)={int(ox)}{flag}")
    return out

# ---- 후보 정의 ----
def f_xor_rot(a):       return lambda x, n: x ^ rotl(x, a, n)
def f_add_rot(a):       return lambda x, n: (x + rotl(x, a, n)) & MASK(n)
def f_xor_rot2(a, b):   return lambda x, n: x ^ rotl(x, a, n) ^ rotl(x, b, n)
# add-rotate-add (carry 비선형 주입): θ(x) = (x ⊞ ROTL_a(x)) ⊞ c  -- 보통 비치환
def f_addrot_c(a, c):   return lambda x, n: ((x + rotl(x, a, n)) + (c & MASK(n))) & MASK(n)
# 회전+xor 합성: θ(x) = ROTL_a(x ⊞ c) ⊕ x   (탐색용)
# "lane orthomorphism" 핵심 후보:
#   θ(x) = ROTL_a(x) ⊞ ROTL_b(x) ⊞ ... 형 (선형이라 보통 실패) 대신
#   carry 가 orthomorphism 깨는 비선형 주입.
# 알려진 결과: (Z/2^n, ⊞) 위 가산 orthomorphism 은 x↦c·x (c,c-1 홀수) 필요 → 불가.
#   그러나 *비선형* T-함수 orthomorphism 은 존재. 후보:
def f_Tfunc1(a):
    """θ(x) = x ⊞ (ROTL_a(x) | const)  류 비선형 — 탐색"""
    return lambda x, n: (x + (rotl(x, a, n) | 1)) & MASK(n)
# XOR-도메인 orthomorphism: GF(2)-선형 M 으로 M, M⊕I 둘 다 가역이면 XOR-orthomorphism.
#   x ⊕ ROTL_a ⊕ ROTL_b 형에서 M=I⊕R^a⊕R^b, M⊕I=R^a⊕R^b 가 둘 다 가역인 (a,b) 탐색.
def f_xor_two(a, b):    return lambda x, n: x ^ rotl(x, a, n) ^ rotl(x, b, n)
def f_xor_three(a,b,c): return lambda x, n: x ^ rotl(x,a,n) ^ rotl(x,b,n) ^ rotl(x,c,n)

if __name__ == "__main__":
    print("== (1a) 단항 선형 ARX (반례 확증) ==")
    for a in (1, 3, 5, 7, 8, 9):
        survey(f"x ^ ROTL_{a}(x)", f_xor_rot(a), ns=(8, 16))
    print()
    for a in (1, 3, 5, 7):
        survey(f"x + ROTL_{a}(x)", f_add_rot(a), ns=(8, 16))

    print("\n== (1b) XOR-도메인 orthomorphism 탐색 (M 과 M⊕I 둘 다 가역) ==")
    # n=8,16 에서 θ⊕id 가 치환이 되는 (a,b)/(a,b,c) 를 찾는다.
    found = []
    for a in range(1, 8):
        for b in range(a + 1, 9):
            r = survey(f"x ^ ROTL_{a} ^ ROTL_{b}", f_xor_two(a, b), ns=(8, 16))
            if all(rr[1] and rr[3] for rr in r):   # perm & θ⊕id perm at all n
                found.append(("two", a, b))
    print(f"  XOR-orthomorphism (θ⊕id perm) 후보 (two-term): {found}")

    print("\n== (1c) 3-term XOR (홀수 항으로 all-ones 커널 회피) ==")
    found3 = []
    for a in range(1, 6):
        for b in range(a + 1, 7):
            for c in range(b + 1, 8):
                r = survey(f"x^R{a}^R{b}^R{c}", f_xor_three(a, b, c), ns=(8, 16))
                if all(rr[1] and rr[3] for rr in r):
                    found3.append((a, b, c))
    print(f"  XOR-orthomorphism (θ⊕id perm) 후보 (three-term): {found3}")

    print("\n== (1d) 비선형 add-기반 후보 ==")
    for a in (1, 3, 5):
        survey(f"x + (ROTL_{a}(x)|1)", f_Tfunc1(a), ns=(8, 16))
