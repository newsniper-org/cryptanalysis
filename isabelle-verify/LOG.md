# Isabelle/HOL 형식 검증 빌드 로그

> 본 파일은 Q1·Q2의 *최종* 검증 결과를 기록한다.
> Theory 파일이 변경되면 본 로그도 갱신할 것.

## 환경
- Isabelle 버전: **Isabelle2025-2**
- 위치: `/opt/isabelle/bin/isabelle` (= `/usr/bin/isabelle` symlink)
- ML 런타임: `polyml-5.9.2_x86_64_32-linux`
- 호스트: `cachyos-ybi-tuf`

## Session 구성
- 이름: `YSC_Probe`
- 부모 session: `HOL-Library`
- Theory: `GF64.thy → Q1_Primitivity.thy → Q2_Cycles.thy`

## 결과

*(빌드 완료 시 채울 예정)*

### Q1 — α primitivity
- `Q1_alpha_pow_N_div_3`: ?
- `Q1_alpha_pow_N_div_5`: ?
- `Q1_alpha_pow_N_div_17`: ?
- `Q1_alpha_pow_N_div_257`: ?
- `Q1_alpha_pow_N_div_641`: ?
- `Q1_alpha_pow_N_div_65537`: ?
- `Q1_alpha_pow_N_div_6700417`: ?
- `Q1_alpha_pow_N_eq_one`: ?
- `Q1_primitive_certificate`: ?

### Q2 — 차수 분포
- `Q2_gcd_table`: ?
- `Q2_ysc4_min_order_lower_bound`: ?
- `Q2_all_orders_practical`: ?

## 트러블슈팅 메모
- Cartouche `‹...›` (U+2039/U+203A) 사용 시 `Malformed command syntax` 에러 →
  ASCII-only `(* ... *)` comments + `\<noteq>`/`\<and>` 사용으로 우회.
- 중위 연산자 `AND`/`XOR` 인식 안 됨 →
  `Bit_Operations.xor`, `Bit_Operations.and` prefix 함수로 대체.
- `HOL-Library` parent session으로 두면 처음 빌드 시 HOL-Library 자체를 빌드해야 함
  (Word, Code_Numeral 등 종속 포함). 캐시 후에는 즉시 사용.

## 인용 (NOTE 회피)

본 검증이 성공할 경우, `farfalle-gen/NOTE-orthomorphism-roll-coincidence.md` §6의 가정 Q1·Q2는
*기계 검증된 사실*로 격상되며, YSC5 사양서에서 인용 가능하다.
