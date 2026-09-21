# 동일 부품 내부의 외벽 틈 보강 — 인쇄 안내

요구사항: `CON-ARCH-006`, `OPS-ARCH-006`.

현재 파일의 게시 여부는 `kc2_wall_gap_fix_manifest.json` 및 아래 검증으로
확인합니다. manifest가 없거나 검증이 실패하면 아직 게시가 완료되지 않은 상태입니다.

```powershell
python -B -m tools.publish_kc2_wall_gap_fix
```

좌우 상판·하판의 기존 구조와 외벽 사이에 남은 불필요한 가느다란 틈을
재료로 채워 연결했습니다. 상판과 하판 사이의 0.30 mm 조립 여유, 오른쪽
A/B 분할 여유, 중앙 맞댐면, 기능상 필요한 스위치·소켓·나사·서비스 공간은
보존합니다. 외벽 높이는 Z5.60, PCB 윗면보다 1.50 mm 높은 상태를 유지합니다.
PCB 받침 높이와 1.60 mm PCB 두께도 그대로입니다.

이는 기존 나사식 구조의 보강입니다. 슬라이드 클립을 사용하지 않습니다.
일반형과 기존 좌우 결합용 자석형 하판 두 종류를 유지합니다.

## 파일 선택

STL, STEP, Fusion F3D는 모두 `hardware/MODELS` 바로 아래에 있습니다.
상판 한 종류와 하판 한 종류를 선택하고 각 행의 세 파일을 인쇄합니다.

| 부품 | 왼쪽 | 오른쪽 A | 오른쪽 B |
|---|---|---|---|
| MX 상판 | `kc2_left_mx_upper_housing.stl` | `kc2_right_mx_upper_housing_part_a.stl` | `kc2_right_mx_upper_housing_part_b.stl` |
| Choc V1 상판 | `kc2_left_choc_v1_upper_housing.stl` | `kc2_right_choc_v1_upper_housing_part_a.stl` | `kc2_right_choc_v1_upper_housing_part_b.stl` |
| Deep Sea Mini 상판 | `kc2_left_deep_sea_upper_housing.stl` | `kc2_right_deep_sea_upper_housing_part_a.stl` | `kc2_right_deep_sea_upper_housing_part_b.stl` |
| 일반 하판 | `kc2_left_lower_housing.stl` | `kc2_right_lower_housing_part_a.stl` | `kc2_right_lower_housing_part_b.stl` |
| 자석형 하판 | `kc2_left_lower_housing_magnetic.stl` | `kc2_right_lower_housing_part_a_magnetic.stl` | `kc2_right_lower_housing_part_b_magnetic.stl` |

총 15개 STL 중 사용 조합에 해당하는 6개를 선택합니다. 오른쪽 STEP/F3D는
A/B 두 몸체를 포함하므로 150 mm 프린터에서는 분리된 STL을 사용합니다.

## 인쇄와 조립

- mm, 배율 100%. 하판은 바닥면을 베드에 놓습니다.
- 상판은 넓은 판 윗면이 베드 쪽을 향하는 방향을 검토합니다. 저상형 나사
  보스 때문에 국소 지지가 필요한지는 슬라이서에서 확인합니다.
- PCB를 기존 받침에 얹고 상판을 수직으로 내려 조립합니다. 불필요한 내부 틈과
  서로 다른 부품 사이의 조립 여유를 혼동하여 강제로 눌러 끼우지 마십시오.
- MX 설계 나사는 M1.4×7.50 mm, 저상형은 M1.4×5.00 mm입니다.
  길이는 머리 아래부터이며 머리 범위는 Ø3.00×높이1.20 mm 이하인 둥근머리입니다.
  실제 나사 제품과 플라스틱 체결성 검증은 별도입니다.
- 기존 Choc V1 링 어댑터 높이와 Deep Sea Mini 가족 구분은 이전 안내와 같습니다.

STL은 수정된 STEP를 Fusion에 가져와 실제 F3D로 저장하고, 그 F3D를 다시
열어 mm 단위로 내보냅니다. 단일체·폐쇄 메시와 실제 단면, 조립 경로 검사는
출력물의 강도·피로·끼움 공차에 대한 실물 합격을 대신하지 않습니다.

이전 `PRINT-wrap-housings.md`와 wrap manifest는 보강 전 이력입니다.
보강 전 단순 재변환 폴더의 STL 대신 이 안내가 지정한 루트 STL을 사용합니다.
검증 근거는 `docs/reports/wall-gap-fix-20260921/`에 있습니다.
