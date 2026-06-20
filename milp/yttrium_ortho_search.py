#!/usr/bin/env python3
"""
ARX/GF orthomorphism 광역 탐색 (n=8,16 전수).

orthomorphism σ 정의(가법군 Z/2^n):  σ 와  x ↦ σ(x) ⊟ x  가 둘 다 치환.
(Lai-Massey 가역의 충분조건이자, signed-sum 불변 Σε_i x_i 를 prob-1 로 깨는 도구.)

여기서는 다음을 한 번에 확인한다:
  (A) GF(2^n) α-곱 (현행 σ): orthomorphism? (가법군 기준 σ⊟id, σ⊕id 둘 다)
  (B) GF(2^n) α-곱 + 회전/상수 ARX 결합으로 ⊟-orthomorphism 회복 시도.
  (C) "XOR-orthomorphism" 정의 (가법을 ⊕ 로): σ, σ⊕id 둘 다 치환 → 충분.
      GF(2^n) α-곱이 자동으로 XOR-orthomorphism 임을 확인 (LM over (F_2^n, ⊕)).
  (D) 순수 ARX 후보: ROTL_a(x) ⊞ c , x ⊞ ROTL_a(x) ⊞ c 등 상수 포함.
"""

MASK = lambda n: (1 << n) - 1
def rotl(x, k, n):
    k %= n
    return ((x << k) | (x >> (n - k))) & MASK(n)

# GF(2^n) reduction polynomials (primitive) for small n (x*α = x<<1 ^ (red if msb)):
RED = {4: 0b0011, 8: 0b00011011, 16: 0b00101101}  # x^4+x+1, x^8+x^4+x^3+x+1, x^16+x^5+x^3+x^2+1(approx)
# Use simple primitive: n=8 -> 0x1B (AES), n=16 -> 0x002D, n=4 -> 0x3
def gf_mul_alpha(x, n, red):
    top = (x >> (n - 1)) & 1
    return ((x << 1) & MASK(n)) ^ (red if top else 0)
def gf_mul_alpha_p(x, p, n, red):
    for _ in range(p):
        x = gf_mul_alpha(x, n, red)
    return x

def is_perm(f, n):
    seen = bytearray(1 << n)
    for x in range(1 << n):
        y = f(x, n) & MASK(n)
        if seen[y]: return False
        seen[y] = 1
    return True

def report(name, f, n):
    p = is_perm(f, n)
    sub = is_perm(lambda x, nn: (f(x, nn) - x) & MASK(nn), n) if p else False
    xor = is_perm(lambda x, nn: (f(x, nn) ^ x) & MASK(nn), n) if p else False
    tag = []
    if p and sub: tag.append("ADD-ORTHO")
    if p and xor: tag.append("XOR-ORTHO")
    print(f"  {name:36s} n={n}: perm={int(p)} σ⊟id={int(sub)} σ⊕id={int(xor)}  {' '.join(tag)}")
    return (p, sub, xor)

if __name__ == "__main__":
    for n in (8, 16):
        red = RED[n]
        print(f"== n={n}, GF red={hex(red)} ==")
        # (A) α-곱 (현행 σ), 거듭제곱 1,3,5,7
        for p in (1, 3, 5, 7):
            report(f"GF α^{p}·x", lambda x, nn, p=p, red=red: gf_mul_alpha_p(x, p, nn, red), n)
        # (D) 순수 ARX 상수 포함
        for a in (1, 3, 5, 7):
            for c in (1, 3):
                report(f"ROTL_{a}(x)+{c}", lambda x, nn, a=a, c=c: (rotl(x, a, nn) + c) & MASK(nn), n)
        for a in (1, 3, 5):
            report(f"x+ROTL_{a}(x)+1", lambda x, nn, a=a: (x + rotl(x, a, nn) + 1) & MASK(nn), n)
        # (B) α-곱 ⊞ 상수 (가법 orthomorphism 회복 시도)
        for p in (1, 3):
            for c in (1, 3):
                report(f"GFα^{p}·x +{c}", lambda x, nn, p=p, c=c, red=red: (gf_mul_alpha_p(x, p, nn, red) + c) & MASK(nn), n)
        print()
