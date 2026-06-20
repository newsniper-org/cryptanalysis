#!/usr/bin/env python3
"""
yttrium-LM (권고안) 가역성 검증 — n=16 축소판 영합 Lai-Massey 라운드.

권고 라운드(폭 n, 워드수 w 파라미터화):
  (ι)        state[r mod w] ⊕= RC[r]
  reduction  xp_i = ROTL_a(x_i);  S = Σ_i ε_i·xp_i (mod 2^n), Σε=0
  combiner   t = F(S);  y_i = ROTR_b(xp_i ⊞ t)
  σ          y_i ← α^{k_i}·y_i  ∀i (GF(2^n) α-곱, red)
  π          new_i = y_{P[i]}

가역의 근거(구조): 영합 Σε=0 이 broadcast t를 부호합에서 상쇄 ⟹ 출력만으로
  S = Σ_i ε_i·ROTL_b(y_i) 를 정확 복원 ⟹ t=F(S) 재평가 ⟹ xp_i=ROTL_b(y_i)⊟t ⟹ x_i=ROTR_a(xp_i).
F·G의 가역성은 전혀 쓰지 않음(Lai-Massey).

검증 항목:
  [1] σ=α^k orthomorphism 분류 (전수): perm / XOR-orthomorphism(α^k(x)⊕x 치환) / 가산-orthomorphism.
  [2] α^{-1} 정확성 (전수): α^{-k}∘α^k = id.
  [3] 영합 S 보존 항등식 (무작위/전수): Σε_i·ROTL_b(y_i) == S.
  [4] 전체 라운드 전단사 (소규모 전수) + roundtrip (n=16 무작위).
  [5] 가역 필수조건 Σε=0 (control): Σε≠0 이면 비전단사.
  [6] '임의 F·비가역 G에도 가역' (control): garbage F 로도 전단사.

정직: n=16/소규모 전수 + 구조적 항등식. n=32 자체 전수는 불가(오케스트레이터 GPU 몫).
실행: python3 yttrium_lm_invert.py   (GPU 불필요)
"""
import random


def make_alpha(n, red):
    M = (1 << n) - 1

    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))
    return alpha


def make_alpha_inv(n, red):
    M = (1 << n) - 1
    half = 1 << (n - 1)

    def alpha_inv(v):
        # α(y) = (y<<1)^(red if msb else 0). 역: low bit 결정 = (v&1) (red bit0=1 가정).
        if v & 1:
            return ((v ^ red) >> 1) | half
        return v >> 1
    return alpha_inv


def rotl_f(n):
    M = (1 << n) - 1

    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M
    return rotl


def F_full(s, n, rotl):
    # 고정 3-term AND-코어, 회전 오프셋 mod n
    return s ^ (rotl(s, 7) & rotl(s, 17)) ^ (rotl(s, 3) & rotl(s, 21)) ^ (rotl(s, 9) & rotl(s, 29))


def build(n, w, red, a, b, eps, sigma, P, Ffn=None, RC=None):
    M = (1 << n) - 1
    rotl = rotl_f(n)
    alpha = make_alpha(n, red)
    alpha_inv = make_alpha_inv(n, red)

    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    def alfp_inv(v, k):
        for _ in range(k):
            v = alpha_inv(v)
        return v

    F = Ffn if Ffn else (lambda s: F_full(s, n, rotl))
    Pinv = [0] * w
    for i in range(w):
        Pinv[P[i]] = i

    def Sval(state):
        S = 0
        for i in range(w):
            xp = rotl(state[i], a)
            S = (S + xp) & M if eps[i] > 0 else (S - xp) & M
        return S

    def rnd(state, r=0):
        st = list(state)
        if RC is not None:
            st[r % w] ^= RC[r % len(RC)]
        xp = [rotl(st[i], a) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, b) for i in range(w)]
        for (lane, k) in sigma:
            y[lane] = alfp(y[lane], k)
        return [y[P[i]] for i in range(w)]

    def rnd_inv(state, r=0):
        # π^{-1}
        y = [0] * w
        for i in range(w):
            y[P[i]] = state[i]
        # σ^{-1}
        for (lane, k) in sigma:
            y[lane] = alfp_inv(y[lane], k)
        # ROTL_b -> v_i = xp_i ⊞ t
        v = [rotl(y[i], b) for i in range(w)]
        # S 복원 (영합 보존)
        S = 0
        for i in range(w):
            S = (S + v[i]) & M if eps[i] > 0 else (S - v[i]) & M
        t = F(S)
        xp = [(v[i] - t) & M for i in range(w)]
        st = [rotr(xp[i], a) for i in range(w)]
        if RC is not None:
            st[r % w] ^= RC[r % len(RC)]
        return st

    return rnd, rnd_inv, Sval, alpha, alpha_inv, alfp, alfp_inv, M


def check_orthomorphism(n, red, ks):
    """[1][2] α^k perm / XOR-orth / ADD-orth + α^{-1} 정확성. 전수."""
    M = (1 << n) - 1
    alpha = make_alpha(n, red)
    alpha_inv = make_alpha_inv(n, red)

    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v

    def alfp_inv(v, k):
        for _ in range(k):
            v = alpha_inv(v)
        return v
    print(f"== [1][2] orthomorphism 분류 + α^-1 (n={n}, red=0x{red:X}) ==")
    inv_ok = all(alpha_inv(alpha(v)) == v for v in range(1 << n))
    print(f"  α^-1∘α == id (전수): {inv_ok}")
    for k in ks:
        img = [alfp(v, k) for v in range(1 << n)]
        perm = len(set(img)) == (1 << n)
        xor_o = len(set((alfp(v, k) ^ v) for v in range(1 << n))) == (1 << n)
        add_o = len(set(((alfp(v, k) - v) & M) for v in range(1 << n))) == (1 << n)
        kinv_ok = all(alfp_inv(alfp(v, k), k) == v for v in range(1 << n))
        print(f"  k={k:2d}: perm={perm} XOR-orth={xor_o} ADD-orth={add_o} α^-k∘α^k=id={kinv_ok}")
    print()


def check_round(name, n, w, red, a, b, eps, sigma, P, exhaustive_bits=None,
                rnd_trials=40000, Ffn=None, RC=None):
    rnd, rnd_inv, Sval, *_ = build(n, w, red, a, b, eps, sigma, P, Ffn=Ffn, RC=RC)
    print(f"== {name} (n={n} w={w} a={a} b={b}) ==")
    # S 보존 (무작위)
    rng = random.Random(1)
    sok = True
    for _ in range(5000):
        x = [rng.randrange(1 << n) for _ in range(w)]
        # S 보존: forward 후 v_i 합 == S? rnd_inv 내부에서 동일 식이므로 roundtrip가 함의.
        if rnd_inv(rnd(x)) != x:
            sok = False
            break
    # roundtrip (RC 포함 다 라운드)
    rt = True
    for _ in range(rnd_trials):
        x = [rng.randrange(1 << n) for _ in range(w)]
        cur = list(x)
        for r in range(6):
            cur = rnd(cur, r)
        for r in reversed(range(6)):
            cur = rnd_inv(cur, r)
        if cur != x:
            rt = False
            break
    print(f"  roundtrip inv∘fwd==id (단일 5000 + 6라운드 {rnd_trials}): {sok and rt}")
    # 전단사 전수
    if exhaustive_bits is not None and exhaustive_bits <= 24:
        seen = set()
        bij = True
        total = 1 << exhaustive_bits
        for c in range(total):
            st = tuple((c >> (i * n)) & ((1 << n) - 1) for i in range(w))
            o = tuple(rnd(list(st)))
            if o in seen:
                bij = False
                break
            seen.add(o)
        print(f"  전단사 전수 2^{exhaustive_bits}: image={len(seen)}/{total} bij={bij}")
    print()


if __name__ == "__main__":
    PI8 = [7, 4, 1, 6, 3, 0, 5, 2]
    SIG_ALL8 = [(0, 1), (1, 2), (2, 3), (3, 5), (4, 7), (5, 11), (6, 13), (7, 17)]
    EPS8 = [1, -1, 1, -1, 1, -1, 1, -1]

    # [1][2] orthomorphism (n=8 red 0x1D, n=16 red 0x2B) — primitive 무관, ortho 성질만
    check_orthomorphism(8, 0x1D, [1, 2, 3, 5, 7, 11, 13, 17])
    check_orthomorphism(16, 0x2B, [1, 2, 3, 5, 7, 11, 13, 17])

    # [3][4] n=16 권고안(all-8 σ) 가역 — RC 포함
    RC16 = [0x428A, 0x7137, 0xB5C0, 0xE9B5, 0x3956, 0x59F1, 0x923F, 0xAB1C]
    check_round("권고 all-8 σ, n=16", 16, 8, 0x2B, 8, 9, EPS8, SIG_ALL8, PI8, RC=RC16)

    # 전단사 전수: n=3 w=8 = 2^24 (정확 8-레인 설정, 회전 mod 3)
    check_round("권고 설정 전단사 전수 n=3 w=8", 3, 8, 0x3, 8 % 3, 9 % 3, EPS8, SIG_ALL8, PI8,
                exhaustive_bits=24, rnd_trials=2000)

    # 소규모 전수 (n=4 w=4)
    check_round("n=4 w=4 전단사 전수", 4, 4, 0x3, 1, 2,
                [1, -1, 1, -1], [(0, 1), (1, 2), (2, 3), (3, 5)], [3, 0, 1, 2],
                exhaustive_bits=16, rnd_trials=5000)

    # [5] control: Σε≠0 이면 비전단사 (가역 필수조건)
    print("== [5] control: Σε≠0 (비영합) → 비전단사 기대 ==")
    rnd_bad, _, _, *_ = build(4, 4, 0x3, 1, 2, [1, 1, 1, 1],
                              [(0, 1), (2, 3)], [3, 0, 1, 2])
    seen = set()
    for c in range(1 << 16):
        st = tuple((c >> (i * 4)) & 0xF for i in range(4))
        seen.add(tuple(rnd_bad(list(st))))
    print(f"  Σε=4 (all +1): image={len(seen)}/65536  bij={len(seen)==65536}  (비전단사 기대)\n")

    # [6] control: garbage(비가역) F 로도 라운드 전단사 (Lai-Massey: F 역산 안 함)
    print("== [6] control: 임의·비가역 F 로도 라운드 전단사 기대 ==")
    garbageF = lambda s: ((s * s) ^ (s >> 1)) & 0xF   # 비가역 F
    check_round("garbage F (비가역), n=4 w=4", 4, 4, 0x3, 1, 2,
                [1, -1, 1, -1], [(0, 1), (1, 2), (2, 3), (3, 5)], [3, 0, 1, 2],
                exhaustive_bits=16, rnd_trials=2000, Ffn=garbageF)
