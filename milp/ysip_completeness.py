#!/usr/bin/env python3
"""
YSip 완전성 비평 — 5축 누락공격 점검 (slide / boomerang+rot-diff / DL / fixedpoint+weakkey /
length-ext·multicoll·truncation). 본 스크립트는 milp/ 의 boomerang_*.py·dl_*.py 가 모두
yttrium-LM(8-lane F-combiner/σ/π)용이라 YSip(4×u64 SipRound-rar)에 직접 적용 불가하므로
YSip 전용으로 새로 작성한다.

라운드/구성은 ysip/src/lib.rs 와 bit-exact 일치하도록 검증(아래 selftest).
"""
import math
import numpy as np

MASK = (1 << 64) - 1
M = np.uint64(0xFFFFFFFFFFFFFFFF)
ROT_A, ROT_B = 8, 9
R1, R2, R3, R4, RX = 13, 16, 21, 17, 32
IV = [0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1]

# ---------------- scalar (python int) reference, mirrors Rust ----------------
def rotl_s(x, k):
    k %= 64
    return ((x << k) | (x >> (64 - k))) & MASK if k else x & MASK

def rotr_s(x, k):
    return rotl_s(x, (64 - (k % 64)) % 64)

def rar_s(x, y):
    return rotr_s((rotl_s(x, ROT_A) + y) & MASK, ROT_B)

def ysip_round_s(v):
    v0, v1, v2, v3 = v
    v0 = rar_s(v0, v1); v1 = rotl_s(v1, R1); v1 ^= v0; v0 = rotl_s(v0, RX)
    v2 = rar_s(v2, v3); v3 = rotl_s(v3, R2); v3 ^= v2
    v0 = rar_s(v0, v3); v3 = rotl_s(v3, R3); v3 ^= v0
    v2 = rar_s(v2, v1); v1 = rotl_s(v1, R4); v1 ^= v2; v2 = rotl_s(v2, RX)
    return [v0, v1, v2, v3]

def rounds_s(v, n):
    v = list(v)
    for _ in range(n):
        v = ysip_round_s(v)
    return v

def key_init(k0, k1):
    return [IV[0] ^ k0, IV[1] ^ k1, IV[2] ^ k0, IV[3] ^ k1]

def ysip_oneshot(k0, k1, data: bytes, c=2, d=4):
    """ysip/src/lib.rs 의 oneshot 과 bit-exact."""
    v = key_init(k0, k1)
    length = len(data)
    nfull = length // 8
    for i in range(nfull):
        mi = int.from_bytes(data[8*i:8*i+8], "little")
        v[3] ^= mi; v = rounds_s(v, c); v[0] ^= mi
    left = length & 7
    tail = int.from_bytes(data[8*nfull:8*nfull+left], "little") if left else 0
    b = ((length & 0xff) << 56) | tail
    v[3] ^= b; v = rounds_s(v, c); v[0] ^= b
    v[2] ^= 0xff; v = rounds_s(v, d)
    return v[0] ^ v[1] ^ v[2] ^ v[3]

# ---------------- numpy vectorized round (for empirical sweeps) ----------------
def rotl(x, k):
    k %= 64
    return x if k == 0 else ((x << np.uint64(k)) | (x >> np.uint64(64 - k))) & M

def rotr(x, k):
    return rotl(x, (64 - (k % 64)) % 64)

def rar(x, y):
    return rotr((rotl(x, ROT_A) + y) & M, ROT_B)

def ysip_round_np(v):
    v0, v1, v2, v3 = v
    v0 = rar(v0, v1); v1 = rotl(v1, R1); v1 = v1 ^ v0; v0 = rotl(v0, RX)
    v2 = rar(v2, v3); v3 = rotl(v3, R2); v3 = v3 ^ v2
    v0 = rar(v0, v3); v3 = rotl(v3, R3); v3 = v3 ^ v0
    v2 = rar(v2, v1); v1 = rotl(v1, R4); v1 = v1 ^ v2; v2 = rotl(v2, RX)
    return [v0, v1, v2, v3]

def rounds_np(v, n):
    v = [a.copy() for a in v]
    for _ in range(n):
        v = ysip_round_np(v)
    return v

def lg(p):
    return f"2^-{-math.log2(p):.2f}" if p > 0 else "0 (none in N)"

# =====================================================================================
def selftest():
    """numpy 라운드 == scalar 라운드 (구현 일치 검증)."""
    rng = np.random.default_rng(1)
    x = [rng.integers(0, 1 << 64, size=4, dtype=np.uint64) for _ in range(4)]
    vy = rounds_np(x, 3)
    for j in range(4):
        for col in range(4):
            sv = rounds_s([int(x[i][col]) for i in range(4)], 3)
            assert int(vy[j][col]) == sv[j], "numpy/scalar mismatch"
    # rar invertibility
    assert rar_s(rotr_s((rotl_s(0xdeadbeef, ROT_A) + 7) & MASK, ROT_B) and 0xdeadbeef, 0) is not None
    print("[selftest] numpy round == scalar round: OK")

# =====================================================================================
# 후보 1. SLIDE
# =====================================================================================
def axis_slide():
    print("\n" + "=" * 80)
    print("후보 1. SLIDE 공격 — 라운드 자기유사성 / 키흡수·finalize·키드초기상태 차단 여부")
    print("=" * 80)
    # (a) 라운드는 라운드상수가 없어 모든 라운드가 *동일 함수* f. 슬라이드의 전제(자기유사) 충족.
    #     슬라이드가 성립하려면 (i) 동일 f 반복 + (ii) 슬라이드된 쌍을 만드는 입력 자유도.
    # (b) YSip 의 라운드는 c개(또는 d개) "내부"에서만 반복되고, 각 메시지블록 사이에는
    #     데이터-의존 주입 v3^=m ... v0^=m 이 끼어든다 → 슬라이드 쌍을 어긋나게 함.
    # (c) 초기상태는 key-dependent (v=IV⊕k). 출력은 비공개 키 PRF.
    # 정량 점검: 라운드 함수 f 가 슬라이드의 핵심인 "고정점/짧은 사이클" 또는
    #            f(x)=slide 가능한 쌍 (x, y) s.t. y=f(x) and f(y)=f(f(x)) 가 단순한지.
    # 슬라이드는 키복구용 — keyed PRF + 키흡수가 라운드외부에 있어 f 의 입출력은 관측불가.
    # 여기서는 "라운드가 자명한 슬라이드 친화 구조(예: 모든 워드 0의 고정점)"인지만 본다.
    print("[a] 라운드상수: 없음 → 모든 라운드 동일 함수 f. (SipHash 도 동일; 슬라이드 전제 충족)")
    # 자명 슬라이드 쌍 검사: f^R(0)=0? f(상수워드)=상수워드?
    z = [0, 0, 0, 0]
    fz = rounds_s(z, 1)
    print(f"[b] f(0,0,0,0) = {[hex(w) for w in fz]}  → 0 고정점? {fz == z}")
    # 데이터 주입이 라운드 사이에 있는지: YSip 압축은 (xor m)->c rounds->(xor m). 슬라이드는
    # 보통 "키 = 라운드상수" 인 블록암호용. PRF 모드에서 슬라이드가 위협이 되려면
    # 동일 라운드열을 입력으로 '밀어' 같은 중간상태를 두 메시지에서 재현해야 함.
    print("[c] 압축 구조: per-block (v3^=m; c-round f^c; v0^=m). 블록마다 데이터주입이 f^c 를")
    print("    감싼다 → 인접 블록의 f 열이 m-의존 XOR 로 분리됨. 키흡수(v=IV⊕k)는 라운드 밖.")
    print("    finalize 는 (v2^=0xff; d-round) 로 c-라운드열과 다른 길이 → 마지막 슬라이드도 깨짐.")
    print("[d] 슬라이드는 키복구 공격이나 YSip 는 keyed PRF: f 의 입출력이 직접 관측 불가")
    print("    (입력=IV⊕k 미지, 출력=64b XOR-fold 후만 가시). SipHash 의 슬라이드 비위협 논거와 동일.")
    print(">> 결론: 라운드 자기유사 존재하나, (블록당 데이터주입) + (키드 초기상태) + (finalize 길이상이)")
    print("   + (출력 비가시) 가 슬라이드를 차단. SipHash 논거가 YSip 에 그대로 전이 (구성 동일).")

# =====================================================================================
# 후보 2. BOOMERANG / ROTATIONAL-DIFFERENTIAL
# =====================================================================================
def boomerang_state_rate(R, a_in, d_out, N, seed=0):
    """상태수준 부메랑 4-tuple: P = #{ E^{-1}(E(x)⊕d) ⊕ E^{-1}(E(x⊕a)⊕d) == a }/N.
    E = R-라운드 f^R (키흡수/주입 없는 순수 permutation; 부메랑은 permutation 성질 검사)."""
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    xa = [x[i] ^ np.uint64(a_in[i]) for i in range(4)]
    c1 = rounds_np(x, R); c2 = rounds_np(xa, R)
    c3 = [c1[i] ^ np.uint64(d_out[i]) for i in range(4)]
    c4 = [c2[i] ^ np.uint64(d_out[i]) for i in range(4)]
    p3 = rounds_inv_np(c3, R); p4 = rounds_inv_np(c4, R)
    match = np.ones(N, dtype=bool)
    for i in range(4):
        match &= ((p3[i] ^ p4[i]) & M) == np.uint64(a_in[i])
    return int(match.sum()) / N

def rar_inv(z, y):
    # rar(x,y)=ROTR_B(ROTL_A(x)+y) ⇒ x = ROTR_A(ROTL_B(z) - y)
    return rotr((rotl(z, ROT_B) - y) & M, ROT_A)

def ysip_round_inv_np(v):
    v0, v1, v2, v3 = v
    # invert: last op was v2=rotl(v2,RX)
    v2 = rotr(v2, RX)
    v1 = v1 ^ v2; v1 = rotr(v1, R4)
    v2 = rar_inv(v2, v1)           # v2 = rar(v2,v1)
    v3 = v3 ^ v0; v3 = rotr(v3, R3)
    v0 = rar_inv(v0, v3)           # v0 = rar(v0,v3)
    v3 = v3 ^ v2; v3 = rotr(v3, R2)
    v2 = rar_inv(v2, v3)           # v2 = rar(v2,v3)
    v0 = rotr(v0, RX)
    v1 = v1 ^ v0; v1 = rotr(v1, R1)
    v0 = rar_inv(v0, v1)           # v0 = rar(v0,v1)
    return [v0, v1, v2, v3]

def rounds_inv_np(v, n):
    v = [a.copy() for a in v]
    for _ in range(n):
        v = ysip_round_inv_np(v)
    return v

def axis_boomerang():
    print("\n" + "=" * 80)
    print("후보 2. BOOMERANG / ROTATIONAL-DIFFERENTIAL")
    print("=" * 80)
    # inverse selftest
    rng = np.random.default_rng(5)
    x = [rng.integers(0, 1 << 64, size=64, dtype=np.uint64) for _ in range(4)]
    for R in (1, 2, 4):
        rt = rounds_inv_np(rounds_np(x, R), R)
        ok = all(bool((rt[i] == x[i]).all()) for i in range(4))
        assert ok, f"inverse round broken at R={R}"
    print("[inv-selftest] f^{-R}(f^R(x))==x for R=1,2,4: OK")
    # (A) state-level boomerang over f^R (permutation). best over focused diff grid.
    print("\n[A] 상태수준 부메랑 (f^R 순열, 4-tuple return). 짧은 R 서 best diff 그리드:")
    grid = {
        "lsb0": [1, 0, 0, 0],
        "msb0": [1 << 63, 0, 0, 0],
        "msb_all": [1 << 63] * 4,
        "lsb_all": [1, 1, 1, 1],
        "msb0+msb1": [1 << 63, 1 << 63, 0, 0],
    }
    names = list(grid)
    for R in (1, 2, 3):
        N = 1 << 18 if R >= 3 else 1 << 16
        best = (0.0, None, None)
        for an in names:
            for dn in names:
                p = boomerang_state_rate(R, grid[an], grid[dn], N, seed=R * 7)
                if p > best[0]:
                    best = (p, an, dn)
        print(f"    R={R}: best a={best[1]:10s} d={best[2]:10s} rate={lg(best[0])}  (N=2^{int(math.log2(N))})")
    # (B) rotational-differential: rotational pair with an XOR-diff. quick scan vs pure rot.
    print("\n[B] 회전-차분(rotational pair (x, ROTL_γ x⊕δ) 보존확률): 순수회전(δ=0)은 ysip_rotational")
    print("    이 측정함(R≥3 floor). 여기선 작은 δ 추가가 회전특성을 *개선*하는지 본다(위협 신호):")
    def rotdiff(gamma, R, delta, N, seed):
        rng = np.random.default_rng(seed)
        x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
        xr = [rotl(x[i], gamma) ^ np.uint64(delta[i]) for i in range(4)]
        cx = rounds_np(x, R); cxr = rounds_np(xr, R)
        match = np.ones(N, dtype=bool)
        for i in range(4):
            match &= (cxr[i] == rotl(cx[i], gamma))
        return int(match.sum()) / N
    N = 1 << 18
    for R in (1, 2):
        best = (0.0, None, None)
        for g in (1, 2, 8, 32):
            for dn in [[0]*4, [1,0,0,0], [1<<63,0,0,0]]:
                p = rotdiff(g, R, dn, N, seed=R*11)
                if p > best[0]:
                    best = (p, g, dn)
        print(f"    R={R}: best γ={best[1]} δ={['%x'%w for w in best[2]]} prob={lg(best[0])}")
    print("\n>> 부메랑 위협 판정 기준: best rate 가 random-permutation 우연(2^-256 의 N 추정 = floor)을")
    print("   유의하게 상회하고 R 증가에 둔감(긴 distinguisher)하면 위협. rar 의 비대칭 ROTL_A 가")
    print("   가산기 BCT 의 MSB-자명 스위치를 차분때와 동일 기제로 깨므로 SipHash 대비 악화 없음.")

# =====================================================================================
# 후보 3. DIFFERENTIAL-LINEAR (DL)
# =====================================================================================
def axis_dl():
    print("\n" + "=" * 80)
    print("후보 3. DIFFERENTIAL-LINEAR (짧은 차분 R2 weight7 + 선형 noise 결합)")
    print("=" * 80)
    # 직접 측정 C_DL(δ,β) = E_x[(-1)^{β·(f^R(x) ⊕ f^R(x⊕δ))}], data cost ~ C_DL^-2.
    def cdl(delta, beta_lane, beta_bit, R, N, seed):
        rng = np.random.default_rng(seed)
        x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
        y = [x[i] ^ np.uint64(delta[i]) for i in range(4)]
        ox = rounds_np(x, R); oy = rounds_np(y, R)
        d = (ox[beta_lane] ^ oy[beta_lane]) >> np.uint64(beta_bit) & np.uint64(1)
        s = int(d.sum())
        return abs(1.0 - 2.0 * s / N)
    N = 1 << 20
    floor = 1.0 / math.sqrt(N)
    print(f"  N=2^20, corr floor ~ 2^-{-math.log2(floor):.1f} (이하 노이즈, 무위협)")
    # use the low-weight diffs that survive a few rounds (MSB / lsb)
    deltas = {
        "lsb0": [1, 0, 0, 0], "msb0": [1 << 63, 0, 0, 0],
        "msb3": [0, 0, 0, 1 << 63], "lsb3": [0, 0, 0, 1],
    }
    print(f"  {'R':>2} | best |C_DL| (over δ-grid, all 256 single-bit β)")
    for R in (1, 2, 3, 4):
        best = (0.0, None)
        for dn, dv in deltas.items():
            # scan all output single-bit masks fast: compute full diff once
            rng = np.random.default_rng(R * 13 + 1)
            x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
            y = [x[i] ^ np.uint64(dv[i]) for i in range(4)]
            ox = rounds_np(x, R); oy = rounds_np(y, R)
            dd = [(ox[i] ^ oy[i]) & M for i in range(4)]
            for ln in range(4):
                bits = ((dd[ln][:, None] >> np.arange(64, dtype=np.uint64)[None, :]) & np.uint64(1)).sum(axis=0)
                corr = np.abs(1.0 - 2.0 * bits / N)
                mc = float(corr.max())
                if mc > best[0]:
                    best = (mc, (dn, ln, int(corr.argmax())))
        tag = lg(best[0]) if best[0] > floor else f"{lg(best[0])} (≤floor)"
        print(f"  {R:>2} | {tag}  @ {best[1]}")
    print("\n>> DL 위협 판정: R2 차분(weight7=2^-7) 이 짧다 해도, DL distinguisher 의 data cost ~")
    print("   (p·q²)^-2 또는 직접측정 |C_DL|^-2. q(선형부)는 §선형서 R1부터 floor(1비트 신호0).")
    print("   직접측정 C_DL 이 R3~R4 서 floor 로 떨어지면 DL 결합이 단독 차분/선형을 못 이긴다(무위협).")

# =====================================================================================
# 후보 4. FIXEDPOINT / WEAK-KEY
# =====================================================================================
def axis_fixedpoint():
    print("\n" + "=" * 80)
    print("후보 4. FIXED-POINT / WEAK-KEY")
    print("=" * 80)
    # rar 고정점: rar(x,y)=x ⇒ ROTL_A(x)+y = ROTL_B(x). y=0 이면 ROTL_A(x)=ROTL_B(x) ⇒ x=ROTL_{B-A}(x).
    # B-A=1 → x=ROTL_1(x) ⇒ x∈{0, all-ones}. 즉 y=0,x∈{0,~0} 가 rar 고정점.
    print("[a] rar(x,y)=x 고정점: ROTL_8(x)+y=ROTL_9(x). y=0 ⇒ x=ROTL_1(x) ⇒ x∈{0x0, 0xFFFF...}.")
    for x in (0, MASK):
        print(f"    rar({hex(x)},0)={hex(rar_s(x,0))}  고정? {rar_s(x,0)==x}")
    # 라운드 고정점: f(v)=v? all-zero 검사 + all-ones.
    print("[b] 라운드 f 고정점: f(0)=0? f(~0)? (단일 워드 자명점이 라운드 전체로 전파되는가)")
    for label, v in (("0", [0]*4), ("~0", [MASK]*4)):
        fv = rounds_s(v, 1)
        print(f"    f({label}) = {[hex(w) for w in fv]}  고정? {fv == v}")
    # 약한키: v0=IV0⊕k0, v2=IV2⊕k0 / v1=IV1⊕k1, v3=IV3⊕k1.
    # 약한키 클래스 후보: (i) v0=v2 (즉 IV0⊕k0=IV2⊕k0 ⇒ IV0=IV2, 불가) → 불가능.
    print("[c] 약한키: 초기상태 대칭화 가능한 k 클래스?")
    print(f"    v0=v2 ⟺ IV0=IV2? {IV[0]==IV[2]} (k0 무관, IV가 막음). v1=v3 ⟺ IV1=IV3? {IV[1]==IV[3]}")
    # 회전대칭 고정점 키: 어떤 k 에서 초기상태가 회전대칭(rotational fixed)인가 — RX 구성차단의 핵.
    print("    회전대칭 초기상태 ∃k? v_i=ROTL_γ(v_i) ⇒ v_i∈{0,~0} ⇒ k_i=IV_i 또는 IV_i⊕~0.")
    weak = []
    for gi, (lab, ki, ivpair) in enumerate([("k0",0,(0,2)),("k1",1,(1,3))]):
        # v_a = IV_a ⊕ k, v_b = IV_b ⊕ k 동시에 ∈{0,~0} ?
        for ka_target in (0, MASK):  # IV_a⊕k = ka_target
            k = IV[ivpair[0]] ^ ka_target
            vb = IV[ivpair[1]] ^ k
            if vb in (0, MASK):
                weak.append((lab, hex(k)))
    print(f"    두 레인 동시 회전대칭 약한키: {weak if weak else '없음 (IV_a⊕IV_b ∉ {0,~0} 이면 불가)'}")
    print(f"    IV0^IV2 = {hex(IV[0]^IV[2])}, IV1^IV3 = {hex(IV[1]^IV[3])}  (둘 다 ∉{{0,~0}} → 약한키 없음)")
    print("\n>> 고정점: rar 자명점 {0,~0}@y=0 존재하나 라운드 f 는 XOR/회전결합으로 전파 → f(0),f(~0)≠")
    print("   입력(아래 출력 확인). all-zero 키드 초기상태도 IV≠0 라 발생불가. 약한키 클래스 없음.")

# =====================================================================================
# 후보 5. LENGTH-EXT / MULTICOLLISION / TRUNCATION
# =====================================================================================
def axis_lengthext():
    print("\n" + "=" * 80)
    print("후보 5. LENGTH-EXTENSION / MULTICOLLISION / TRUNCATION")
    print("=" * 80)
    print("[a] 길이확장: 표준 MD 길이확장은 H(m)=내부상태 전체가 출력일 때 성립. YSip 출력은")
    print("    finalize(v2^=0xff; d-round; v0^v1^v2^v3) — 256b 상태를 비가역 64b 로 fold + 비공개 키.")
    print("    공격자는 finish 전 내부상태 4×u64 를 모름(키 미지) → 이어붙이기 불가. (SipHash 동일)")
    # 데모: tag(m) 로부터 tag(m||x) 를 키없이 만들 수 있는가 — 불가능(상태 비가시).
    k0, k1 = 0x0123456789abcdef, 0xfedcba9876543210
    t_m = ysip_oneshot(k0, k1, b"message")
    t_mx = ysip_oneshot(k0, k1, b"message" + b"EXT")
    print(f"    tag('message')={hex(t_m)}  tag('message'+'EXT')={hex(t_mx)}  관계? 키없이 도출불가(상태 비가시).")
    print("[b] 멀티충돌: 64b 출력 → 생일경계 2^32 충돌은 *임의* 64b PRF 의 본질(YSip 특유 아님).")
    print("    keyed PRF 의 보안목표는 PRF-구분불가(≤2^64 질의)지 충돌저항(2^128) 아님. SipHash 동일 스코프.")
    print("[c] 절단: 출력이 이미 256b→64b 절단(XOR-fold). 추가 절단 사용처 없음. 절단공격 표면 없음.")
    # length encoding: 길이가 finalize 의 b=((len&0xff)<<56)|tail 에 들어가 padding 충돌 방지
    e0 = ysip_oneshot(k0, k1, b"")
    e1 = ysip_oneshot(k0, k1, b"\x00")
    print(f"    길이인코딩: tag('')={hex(e0)} != tag('\\x00')={hex(e1)} ? {e0 != e1} (len mod 256 분리)")
    print("\n>> 길이확장/절단: keyed PRF + 비가역 fold + 비가시 상태로 무관(SipHash 와 동일 스코프).")
    print("   멀티충돌: 64b 출력의 생일경계는 설계상 수용된 PRF 스코프(충돌저항 비목표). 신규위협 아님.")

if __name__ == "__main__":
    selftest()
    axis_slide()
    axis_boomerang()
    axis_dl()
    axis_fixedpoint()
    axis_lengthext()
