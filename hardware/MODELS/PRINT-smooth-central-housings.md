# 중앙 요철 자리를 메운 최신 하판

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

기존 요철 중심 Y=95,117 mm에서 남아 있던 파임을 메웠습니다. 주변과 같은 외벽 두께 1.20 mm, 바닥 Z=-2.20..-1.00 mm를 사용하여 요철 자리가 매끄럽게 이어집니다. 벽 밖으로 돌출시키거나 좌우 위치를 바꾸지 않았습니다.

하판은 아래 두 종류 중 하나의 세 파일을 인쇄하십시오. 모두 이 디렉터리에 있습니다.

| 종류 | 왼쪽 | 오른쪽 A | 오른쪽 B |
|---|---|---|---|
| 일반형 | [STL](kc2_left_lower_housing.stl) | [STL](kc2_right_lower_housing_part_a.stl) | [STL](kc2_right_lower_housing_part_b.stl) |
| 자석형 | [STL](kc2_left_lower_housing_magnetic.stl) | [STL](kc2_right_lower_housing_part_a_magnetic.stl) | [STL](kc2_right_lower_housing_part_b_magnetic.stl) |

자석형은 기존 두 쌍(Y=103,111 mm), Ø2 mm × 1 mm 자석과 Ø2.4 mm × 1.2 mm 홈을 사용합니다. 컨트롤러 쪽 세 번째 홈은 없습니다. 접착 전에 좌우 극성을 맞추십시오.

단위 mm, 배율 100%, 평평한 바닥면을 베드에 놓습니다. 상판은 기존 MX/Choc V1/Deep Sea Mini 중 실제 스위치에 맞는 종류를 사용합니다. PCB는 하판 받침 위에 올립니다. 상판별 나사·출력 조건은 [상판 조립 안내](PRINT-registered-housings.md)를 참고하되 하판 파일과 현재 검증은 이 문서를 따르십시오.

```powershell
python -B -m tools.publish_kc2_smooth_central_seam --verify
```

상태는 `digitally_verified_physical_pending`입니다. 실제 출력 강도와 끼움·자석 고정력은 출력 후 확인해야 합니다.
