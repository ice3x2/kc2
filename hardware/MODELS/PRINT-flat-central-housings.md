# 평평한 중앙 이음 하우징 인쇄 안내

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

## 이번 개정

- 좌우 키보드 중앙 이음의 요철 두 쌍(`Y=95, 117 mm`)을 일반형·자석형 하판에서 모두 제거했습니다.
- 중앙 면은 잠금이나 억지 끼움이 없는 평평한 비접촉 면입니다.
- 기존 소켓 가림벽, PCB 받침, 바닥, 70개 키 지지부, 17개 나사 위치, 우측 A/B 결합부와 상·하판 위치맞춤 구조는 유지했습니다.
- 자석형의 기존 두 자석 쌍(`Y=103, 111 mm`)은 그대로입니다.
- 컨트롤러 쪽 세 번째 자석 쌍은 추가하지 않았습니다. 가장 가까운 후보도 필요한 잔여 재료가 부족했고, 안전한 후보는 자석 면 사이가 약 `31.91 mm`라 실질적인 흡착 위치가 아니었습니다. 벽 확장은 사용자가 금지했으므로 무리하게 넣지 않았습니다.

## 인쇄 파일

하판은 일반형 또는 자석형 중 하나만 인쇄합니다.

| 종류 | 왼쪽 1개 | 오른쪽 2개 |
|---|---|---|
| 일반형 | `kc2_left_lower_housing.stl` | `kc2_right_lower_housing_part_a.stl`, `kc2_right_lower_housing_part_b.stl` |
| 자석형 | `kc2_left_lower_housing_magnetic.stl` | `kc2_right_lower_housing_part_a_magnetic.stl`, `kc2_right_lower_housing_part_b_magnetic.stl` |

상판은 실제 스위치에 맞춰 MX, Choc V1, Deep Sea Mini 중 하나만 고릅니다. 오른쪽은 항상 A/B 두 STL을 인쇄합니다.

## 기본 설정과 조립 확인

- 단위 mm, 배율 100%로 슬라이싱합니다.
- 오른쪽 A/B는 서로 다른 부품이므로 각각 평평한 바닥면을 베드에 놓습니다.
- 중앙의 평평한 면을 서포트처럼 인식해 얇은 구조가 생기지 않는지 미리보기를 확인합니다.
- 자석형은 지름 2 mm, 두께 1 mm 원통형 자석을 기존 지름 2.4 mm, 깊이 1.2 mm 홈에 접착 고정합니다. 좌우 극성을 먼저 맞춥니다.
- 세 번째 자석 홈을 수작업으로 추가하거나 기존 홈을 넓히지 마십시오.
- PCB를 하판 받침 위에 올린 뒤 선택한 상판을 덮고 지정 나사를 조입니다. 나사로 억지 정렬하지 마십시오.
- 처음에는 시험 출력으로 중앙 간격, 오른쪽 A/B 결합, PCB 안착, 소켓·배선 간섭을 확인합니다.

검증 명령:

```powershell
python -B -m tools.publish_kc2_flat_central_housings --verify hardware/MODELS/kc2_flat_central_housing_manifest.json
```

현재 manifest의 상태는 `digitally_verified_physical_pending`입니다. 출력 팽창·수축, 자석 유지력과 실제 조립 감각은 시험 출력 후 확인해야 합니다.
