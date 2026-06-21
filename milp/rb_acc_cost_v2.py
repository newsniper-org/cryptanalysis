#!/usr/bin/env python3
"""
R_b — acc-충돌 비용 (정정판). aligned-pair 비용은 1/best-DP (제곱 아님)이 맞다.

정정 근거: 슬롯 j,j' 둘 다 차분 Δ를 받고, 출력차 ∇이 동일하길 원한다(XOR소거).
  - 단일 지배 ∇*(prob p=best-DP)로 둘 다 맞추려면, 각 슬롯에서 입력을 ~1/p 시도.
    하지만 한 슬롯에서 ∇* 한 번 찾으면 그 ∇*는 고정; 다른 슬롯도 ∇* 찾으면 됨.
    => 작업 = 1/p (슬롯A에서 ∇* 1개) + 1/p (슬롯B에서 ∇* 1개) ≈ 2/p ⇒ ~2^{w+1}.
  - 더 일반적으로 birthday: 슬롯A 출력차 리스트 L_A, 슬롯B 리스트 L_B, 충돌 ∇ 찾기.
    출력차 엔트로피가 H면 |L|~2^{H/2}로 birthday. 단 차분특성이 H를 좁히면(저 weight ∇ 집중)
    그 클러스터 안 birthday가 더 싸다. 보수적으로 best-DP 지배 가정: cost ~ 1/best-DP.

따라서 acc-충돌(최소 활성 = 1쌍, 2 슬롯) 작업 하한 ≈ 1/best-DP(R_b).
이게 digest collision 목표 2^64를 넘으려면  best-DP(R_b) <= 2^-64  필요.
(주의: 이건 "한 쌍" 최저비용. T_max=8을 다 활성화한 Wagner 변형은 256-bit폭이 받쳐 더 비쌈.)
"""
import math

if __name__=="__main__":
    print("=== acc-충돌(aligned-pair) 작업 = 1/best-DP(R_b) (정정) ===")
    print("    목표: best-DP(R_b) <= 2^-64 이어야 단일쌍 acc-충돌이 birthday(2^64) 이상.\n")
    scenarios = {
        "trail 외삽 per-round +12 (R1=2.6; n=8 slope로 보정 예정)": {1:2.6,2:14.6,3:26.6,4:38.6,5:50.6,6:62.6,7:74.6},
        "보수 per-round +8": {1:2.6,2:10.6,3:18.6,4:26.6,5:34.6,6:42.6,7:50.6,8:58.6,9:66.6},
        "낙관 per-round +15 (full all-8 σ 확산)": {1:2.6,2:17.6,3:32.6,4:47.6,5:62.6},
    }
    for name,dpw in scenarios.items():
        print(f"  [{name}]")
        for R in sorted(dpw):
            w=dpw[R]
            ok = " <=2^-64 OK (collision막힘)" if w>=64 else (" <=2^-128 OK(preimage)" if w>=128 else "")
            print(f"    R_b={R}: best-DP 2^-{w:.1f}{ok}")
        # find first R reaching 64 and 128
        r64=next((R for R in sorted(dpw) if dpw[R]>=64), None)
        r128=next((R for R in sorted(dpw) if dpw[R]>=128), None)
        print(f"    => best-DP<=2^-64 at R_b={r64}; <=2^-128 at R_b={r128}\n")

    print("=== 마진 정책 ===")
    print("  distinguisher(MSB-쌍 best-DP)는 측정상 R=2서 noise floor 붕괴(yttrium_lm_diff.cu).")
    print("  '소멸 라운드의 2배' 마진 => 2*2 = 4. 별개로 trail 외삽상 best-DP<=2^-64는")
    print("  per-round+12 가정서 R~5.5, +8 가정서 R~8.6. 보안목표(collision 2^64)에 R_b=4는")
    print("  외삽 가정에 민감 (낙관/중간 OK, 보수 부족). 아래 판정 참조.")
