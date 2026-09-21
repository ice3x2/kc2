# 상판 내부 틈·공면 하부 개정 인쇄 안내

요구사항: `CON-ARCH-006`, `OPS-ARCH-006`.

게시 완료 여부는 `kc2_upper_finish_manifest.json`과 아래 명령으로 확인합니다.
manifest가 없거나 검증이 실패하면 새 상판 게시가 아직 끝나지 않은 상태입니다.

```powershell
python -B -m tools.publish_kc2_upper_finish
```

MX, Choc V1, Deep Sea Mini 상판을 함께 수정했습니다. 외벽 안쪽의 닫힌 비기능
틈만 연속 재료로 메웠고, 스위치·소켓·나사·서비스·상하판 결합 공간은 보호했습니다.
오른쪽 중앙 A/B 분할 간격은 필요한 기능 공간이므로 유지합니다.

기존 상판은 나사 랜드만 `Z=4.10..4.40`으로 0.30 mm 내려와 있었습니다. 새 상판은
그 국부 하향 돌출을 제거하여 모든 상판 부품의 최저면을 `Z=4.40` 하나로 맞췄습니다.
재료를 아래로 덧붙이지 않았습니다. `Z=4.40` 위의 넓은 나사 보스와 관통 보어는
변경하지 않았습니다.

## 인쇄 파일 선택

파일은 `hardware/MODELS` 바로 아래에 있습니다. 상판 한 종류와 하판 한 종류를
선택하고, 각 손의 왼쪽 한 파일과 오른쪽 A/B 두 파일을 각각 한 개 인쇄합니다.

| 부품 | 왼쪽 | 오른쪽 A | 오른쪽 B |
|---|---|---|---|
| MX 상판 | `kc2_left_mx_upper_housing.stl` | `kc2_right_mx_upper_housing_part_a.stl` | `kc2_right_mx_upper_housing_part_b.stl` |
| Choc V1 상판 | `kc2_left_choc_v1_upper_housing.stl` | `kc2_right_choc_v1_upper_housing_part_a.stl` | `kc2_right_choc_v1_upper_housing_part_b.stl` |
| Deep Sea Mini 상판 | `kc2_left_deep_sea_upper_housing.stl` | `kc2_right_deep_sea_upper_housing_part_a.stl` | `kc2_right_deep_sea_upper_housing_part_b.stl` |
| 일반 하판 | `kc2_left_lower_housing.stl` | `kc2_right_lower_housing_part_a.stl` | `kc2_right_lower_housing_part_b.stl` |
| 자석형 하판 | `kc2_left_lower_housing_magnetic.stl` | `kc2_right_lower_housing_part_a_magnetic.stl` | `kc2_right_lower_housing_part_b_magnetic.stl` |

상판은 `Z=4.40` 공면이 베드에 닿도록 놓는 방향을 권장합니다. 단위는 mm, 배율은
100%입니다. 오른쪽 STEP/F3D에는 A/B 두 몸체가 들어 있으므로 150 mm 프린터에서는
분리된 A/B STL을 사용합니다.

디지털 검증은 실제 프린터의 첫 레이어 접착, 수축·팽창, 나사 토크, 장기 강도와
실장 PCB의 최종 조립 감각을 확정하지 않습니다. 먼저 한 조합을 시험 출력하십시오.
이전 `PRINT-wall-gap-fix.md`와 그 manifest는 이번 공면 개정 전 이력입니다.
