# KC2 현재 하우징 파일

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

현재 인쇄·편집 파일은 이 디렉터리에 바로 있습니다. 하판 외벽을 PCB 윗면보다 1.50 mm 높게 만들어 상판 아래쪽을 1.20 mm 감싸도록 했습니다. PCB 받침 높이·1.60 mm PCB 두께·주문 거버는 그대로입니다. 상판 외곽도 대응하도록 바뀌었으므로 새 상판과 하판을 함께 사용하십시오. 중앙 요철은 복원하지 않았고 기존 소켓 가림벽과 두 자석 쌍은 유지합니다.

현재 상판은 내부 비기능 틈을 메우고 나사 랜드의 0.30 mm 하향 돌출을 제거해 최저면을 `Z=4.40`으로 공면화한 개정입니다. [현재 인쇄 안내](PRINT-upper-finish.md)를 따르십시오. 아래 검증이 통과해야 게시가 완료된 것입니다. manifest가 없거나 실패하면 인쇄를 보류하십시오.

```powershell
python -B -m tools.publish_kc2_upper_finish
```

## 하판 선택

두 종류 중 한 종류만 선택합니다.

| 종류 | 왼쪽 | 오른쪽 A | 오른쪽 B |
|---|---|---|---|
| 일반형 | [STL](kc2_left_lower_housing.stl) | [STL](kc2_right_lower_housing_part_a.stl) | [STL](kc2_right_lower_housing_part_b.stl) |
| 자석형 | [STL](kc2_left_lower_housing_magnetic.stl) | [STL](kc2_right_lower_housing_part_a_magnetic.stl) | [STL](kc2_right_lower_housing_part_b_magnetic.stl) |

자석형은 기존 중앙 하단의 자석 두 쌍(`Y=103, 111 mm`)만 유지합니다. 컨트롤러 쪽 세 번째 쌍은 벽을 넓히지 않고 안전한 잔여 재료와 유효 흡착 거리를 동시에 확보할 수 없어 추가하지 않았습니다. 임의로 구멍을 뚫지 마십시오.

## 상판 선택

MX, Choc V1, Deep Sea Mini 중 실제 스위치와 맞는 한 종류만 선택합니다. 왼쪽은 STL 한 개, 오른쪽은 `part_a`와 `part_b` 두 개입니다. 세 종류 모두 새 외벽과 맞는 외곽 립을 반영했습니다.

- MX: `kc2_left_mx_upper_housing.stl`, `kc2_right_mx_upper_housing_part_a.stl`, `kc2_right_mx_upper_housing_part_b.stl`
- Choc V1: `kc2_left_choc_v1_upper_housing.stl`, `kc2_right_choc_v1_upper_housing_part_a.stl`, `kc2_right_choc_v1_upper_housing_part_b.stl`
- Deep Sea Mini: `kc2_left_deep_sea_upper_housing.stl`, `kc2_right_deep_sea_upper_housing_part_a.stl`, `kc2_right_deep_sea_upper_housing_part_b.stl`

STL은 인쇄용, STEP과 F3D는 편집·검토용입니다. 오른쪽 전체 STEP/F3D에는 두 몸체가 들어 있으므로 150 mm 프린터에서는 반드시 A/B STL을 사용하십시오. 현재 manifest는 `kc2_upper_finish_manifest.json`입니다. 이전 wall-gap/registered/flat-central/smooth-central/wrap manifest와 `STL_FROM_FUSION_20260921`은 비교 이력입니다. 나사식 조립과 실제 상·하판 여유는 유지합니다.

디지털 검증은 실제 출력물의 수축·팽창, 자석 접착력, 장기 강도와 조립 감각을 확정하지 않습니다. 먼저 시험 출력 후 좌우 간격과 자석 극성을 확인하십시오.
