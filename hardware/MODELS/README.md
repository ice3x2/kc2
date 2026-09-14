# KC2 현재 하우징 파일

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

현재 인쇄·편집 파일은 이 디렉터리에 바로 있습니다. 중앙 좌우 결합부의 요철은 모두 제거되었으며, 좌우 하우징의 맞닿는 면은 평평한 비접촉 이음입니다. PCB, Gerber, 상판, 우측 A/B 결합부와 상·하판 위치맞춤 구조는 이번 개정에서 바뀌지 않았습니다.

인쇄 전에 [현재 인쇄 안내](PRINT-flat-central-housings.md)를 읽고 다음 검증을 실행하십시오.

```powershell
python -B -m tools.publish_kc2_flat_central_housings --verify hardware/MODELS/kc2_flat_central_housing_manifest.json
```

## 하판 선택

두 종류 중 한 종류만 선택합니다.

| 종류 | 왼쪽 | 오른쪽 A | 오른쪽 B |
|---|---|---|---|
| 일반형 | [STL](kc2_left_lower_housing.stl) | [STL](kc2_right_lower_housing_part_a.stl) | [STL](kc2_right_lower_housing_part_b.stl) |
| 자석형 | [STL](kc2_left_lower_housing_magnetic.stl) | [STL](kc2_right_lower_housing_part_a_magnetic.stl) | [STL](kc2_right_lower_housing_part_b_magnetic.stl) |

자석형은 기존 중앙 하단의 자석 두 쌍(`Y=103, 111 mm`)만 유지합니다. 컨트롤러 쪽 세 번째 쌍은 벽을 넓히지 않고 안전한 잔여 재료와 유효 흡착 거리를 동시에 확보할 수 없어 추가하지 않았습니다. 임의로 구멍을 뚫지 마십시오.

## 상판 선택

MX, Choc V1, Deep Sea Mini 중 실제 스위치와 맞는 한 종류만 선택합니다. 왼쪽은 STL 한 개, 오른쪽은 `part_a`와 `part_b` 두 개입니다. 상판은 이번 중앙 요철 제거 개정에서 형상이 바뀌지 않았습니다.

- MX: `kc2_left_mx_upper_housing.stl`, `kc2_right_mx_upper_housing_part_a.stl`, `kc2_right_mx_upper_housing_part_b.stl`
- Choc V1: `kc2_left_choc_v1_upper_housing.stl`, `kc2_right_choc_v1_upper_housing_part_a.stl`, `kc2_right_choc_v1_upper_housing_part_b.stl`
- Deep Sea Mini: `kc2_left_deep_sea_upper_housing.stl`, `kc2_right_deep_sea_upper_housing_part_a.stl`, `kc2_right_deep_sea_upper_housing_part_b.stl`

STL은 인쇄용, STEP과 F3D는 편집·검토용입니다. 오른쪽 전체 STEP/F3D에는 두 몸체가 들어 있으므로 150 mm 프린터에서는 반드시 A/B STL을 사용하십시오. 이전 [registered manifest](kc2_registered_housing_manifest.json)는 요철이 있던 직전 판의 이력이며, 현재 manifest는 [flat central manifest](kc2_flat_central_housing_manifest.json)입니다.

디지털 검증은 실제 출력물의 수축·팽창, 자석 접착력, 장기 강도와 조립 감각을 확정하지 않습니다. 먼저 시험 출력 후 좌우 간격과 자석 극성을 확인하십시오.
