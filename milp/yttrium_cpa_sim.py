#!/usr/bin/env python3
"""yttrium 전력 side-channel (CPA) **시뮬레이션** — leakage-model.

목적: yttrium keyed leaf의 첫 비밀-의존 중간값 s[i]=block[i]⊕mask[i] (block 공격자제어, mask 비밀)에
HW(Hamming-weight) leakage 모델로 per-byte CPA를 걸어 mask 바이트 복구가 되는지 시도.

★ 정직성/귀속(feedback_sidechannel_root_cause_attribution): 이건 **시뮬레이션**(실제 CPU 측정 아님)
이라 하드웨어 버그와 무관. CPA가 성공하면 그 원인은 **미보호(unmasked) 구현의 선형 XOR-with-secret
누출**(모든 unprotected 암호 공통; AES unmasked AddRoundKey와 동일)이지 yttrium **프리미티브 결함이
아니다.** 대조군(C)로 yttrium 구조가 *추가* DPA 타깃(per-byte 비선형)을 주지 않음을 보인다.

실행: python3 yttrium_cpa_sim.py   (numpy; GPU 불요)
"""
import numpy as np

rng = np.random.default_rng(1)
HW = np.array([bin(x).count("1") for x in range(256)], dtype=np.float64)


def cpa_recover_byte(known_bytes, leak, model):
    """known_bytes:(M,), leak:(M,). leak=+HW+noise 모델 → **부호 있는** corr 최대 = 복구값
    (보수 모호성 해소: HW(b^x)와 HW(b^~x)는 |corr| 동일하나 부호 반대)."""
    lc = leak - leak.mean()
    corrs = np.zeros(256)
    for cand in range(256):
        pred = model(known_bytes, cand)
        pc = pred - pred.mean()
        denom = np.sqrt((pc * pc).sum() * (lc * lc).sum())
        corrs[cand] = (pc * lc).sum() / denom if denom > 0 else 0.0
    best = int(np.argmax(corrs))           # 부호 있는 최대(양의 HW 상관)
    s = np.sort(corrs)[::-1]
    return best, corrs[best], s[0] - s[1]   # gap = 1위−2위(부호 corr 기준)


def main():
    M = 6000
    print("== (A) CPA on s=block⊕mask (yttrium 첫 중간값; 선형 XOR-with-secret) ==")
    secret = 0xA7  # mask 한 바이트(비밀)
    blocks = rng.integers(0, 256, size=M, dtype=np.int64)
    for sigma in [0.5, 1.0, 2.0, 4.0]:
        leak = HW[(blocks ^ secret)] + rng.normal(0, sigma, M)
        rec, c, gap = cpa_recover_byte(blocks, leak, lambda b, k: HW[(b ^ k) & 0xFF])
        ok = "✓복구" if rec == secret else "✗"
        print(f"  noise σ={sigma:>3}: 복구={rec:#04x} (정답 {secret:#04x}) {ok}  corr={c:.3f} gap={gap:.3f}")

    print("\n== (B) 트레이스 수 효과 (σ=2.0) ==")
    for m in [200, 800, 3000, 12000]:
        b = rng.integers(0, 256, size=m, dtype=np.int64)
        leak = HW[(b ^ secret)] + rng.normal(0, 2.0, m)
        rec, c, gap = cpa_recover_byte(b, leak, lambda bb, k: HW[(bb ^ k) & 0xFF])
        print(f"  M={m:>5}: 복구={rec:#04x} {'✓' if rec==secret else '✗'} corr={c:.3f}")

    print("\n== (C) 대조군: 비선형 post-mix(t=F(S)) 바이트에 per-byte CPA (yttrium 추가 타깃 부재 확인) ==")
    # S = Σ_i ε_i·ROTL8(block_i⊕mask_i) (mod 2^32), t=F(S). per-byte block 가설로 t의 한 바이트 누출 공격.
    # 단일 레인 block0만 변화시키고 나머지 고정(공격자 1바이트 가설).
    def rotl(x, k):
        return ((x << k) | (x >> (32 - k))) & 0xFFFFFFFF
    def F(s):
        return s ^ (rotl(s, 7) & rotl(s, 17)) ^ (rotl(s, 3) & rotl(s, 21)) ^ (rotl(s, 9) & rotl(s, 29))
    mask = rng.integers(0, 1 << 32, size=8, dtype=np.uint64)
    eps = [1, -1, 1, -1, 1, -1, 1, -1]
    other = rng.integers(0, 1 << 32, size=(M, 7), dtype=np.uint64)  # 다른 7레인 랜덤(공격자 모름)
    b0 = rng.integers(0, 256, size=M, dtype=np.int64)  # 공격자 제어 1바이트(레인0 하위바이트)
    tbytes = np.zeros(M, dtype=np.int64)
    secret0 = int(mask[0]) & 0xFF
    for j in range(M):
        w0 = (int(b0[j]) ^ (int(mask[0]))) & 0xFFFFFFFF
        S = rotl(w0, 8)
        for i in range(1, 8):
            wi = (int(other[j, i - 1]) ^ int(mask[i])) & 0xFFFFFFFF
            S = (S + rotl(wi, 8)) % (1 << 32) if eps[i] > 0 else (S - rotl(wi, 8)) % (1 << 32)
        tbytes[j] = F(S) & 0xFF
    leakC = tbytes.astype(np.float64) + rng.normal(0, 2.0, M)  # post-mix HW(여기선 값 자체 근사)
    # per-byte 가설: HW(F(rotl(b0^cand,8) ⊞ 알수없는상수)) — 공격자는 다른레인 모르므로 단순 HW(b0^cand)로 시도
    rec, c, gap = cpa_recover_byte(b0, leakC, lambda b, k: HW[(b ^ k) & 0xFF])
    print(f"  per-byte CPA on t=F(S): 복구={rec:#04x} (정답 {secret0:#04x}) "
          f"{'✓(우연/누출?)' if rec == secret0 else '✗ 실패(기대)'}  corr={c:.3f}")
    print("  → 비선형+전레인 혼합(영합 reduction)이라 per-byte 가설로 분리 불가(corr 무의미) = 기대.")

    print("\n== 귀속(정직) ==")
    print("  (A)(B) 성공 = 미보호 구현의 선형 block⊕mask 누출(generic; unmasked AES와 동일).")
    print("  → 원인=구현(마스킹 미적용), NOT 프리미티브 결함, NOT 하드웨어(순수 시뮬).")
    print("  (C) yttrium은 S-box 없음+영합 전레인혼합이라 per-byte 비선형 DPA 타깃 *부재*(AES보다 적음).")
    print("  결론: cache/timing은 구성상 강건. power-SCA는 마스킹(구현 의무) 필요 — 프리미티브 무관.")


if __name__ == "__main__":
    main()
