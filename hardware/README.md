# 최신 PCB · 주문한 거버 · 인쇄 모델

요구사항: `CON-ARCH-006`, `OPS-ARCH-006/007`.
2026-09-10 국소 가림벽 개정은 기존 r5 하판 위에 PCB를 올리는 구조를 유지합니다.
[현재 인쇄·실장 안내](MODELS/PRINT-local-covers.md)의 게시 검증을 먼저 실행하세요.
자석을 사용할 경우 [자석 홈 옵션 인쇄 안내](MODELS/PRINT_magnetic.md)에서 `_magnetic` 하판 세트를 선택하세요. 두 하판 옵션에 같은 국소 가림부를 적용하며 자석 홈은 그대로 유지합니다.
PCB 설계와 주문된 거버 ZIP은 변경하지 않았습니다. 정확한 주문번호와 업체는 제공되지 않았습니다.

```text
hardware/
├─ PCB/
│  ├─ kc2_left/       왼쪽 KiCad 프로젝트
│  └─ kc2_right/      오른쪽 KiCad 프로젝트
├─ GERBER/            주문한 r4 봉인 패키지(8파일)
└─ MODELS/            현재 하우징 STL·STEP·Fusion F3D
   └─ adapters/       MX/V1 링 STL
```

## PCB 편집·확인

- 왼쪽: [KiCad 프로젝트](PCB/kc2_left/kc2_left.kicad_pro) / [PCB](PCB/kc2_left/kc2_left.kicad_pcb)
- 오른쪽: [KiCad 프로젝트](PCB/kc2_right/kc2_right.kicad_pro) / [PCB](PCB/kc2_right/kc2_right.kicad_pcb)

각 프로젝트 폴더를 통째로 유지하세요. 풋프린트 라이브러리는 저장소 `third_party`를 참조합니다.
PCB 폴더와 `third_party`의 상대 깊이는 이전과 같아 라이브러리 경로 변경이 필요 없습니다.

## 주문한 거버

- [왼쪽 제조 ZIP](GERBER/kc2_left-pcb-fabrication-only.zip)
- [오른쪽 제조 ZIP](GERBER/kc2_right-pcb-fabrication-only.zip)
- [제조 설정](GERBER/fabrication-profile.json) / [검증 manifest](GERBER/manifest.json)
- [왼쪽 수동 BOM](GERBER/kc2_left-manual-mx-bom.json) / [오른쪽 수동 BOM](GERBER/kc2_right-manual-mx-bom.json)

두 ZIP은 주문 당시 `solid-floor-20260907-r4`와 동일합니다. 위치 정리를 이유로 재주문할 필요는 없습니다.
이 디렉토리에 새 파일을 추가하거나 봉인 파일을 수정하지 마세요. 이전 개정은 `hardware/kicad/first_order`에 남아 있습니다.

## 인쇄할 하우징 — 선택한 MX 조립

아래 6개를 각각 1개, mm 단위·100% 축척으로 인쇄합니다.

| 부품 | STL |
|---|---|
| 왼쪽 바닥 일체형 하판 | [왼쪽 하판](MODELS/kc2_left_lower_housing.stl) |
| 오른쪽 하판 A | [오른쪽 하판 A](MODELS/kc2_right_lower_housing_part_a.stl) |
| 오른쪽 하판 B | [오른쪽 하판 B](MODELS/kc2_right_lower_housing_part_b.stl) |
| 왼쪽 MX 보강판 뚜껑 | [왼쪽 상판](MODELS/kc2_left_mx_upper_housing.stl) |
| 오른쪽 MX 뚜껑 A | [오른쪽 상판 A](MODELS/kc2_right_mx_upper_housing_part_a.stl) |
| 오른쪽 MX 뚜껑 B | [오른쪽 상판 B](MODELS/kc2_right_mx_upper_housing_part_b.stl) |

하판은 평평한 바닥 외면을 베드에 놓습니다. 바닥 1.20 mm는 첫 층·후속 층 모두 0.20 mm일 때 6층입니다.
상판은 보강판 윗면을 베드에 놓고 기둥이 위로 향하게 합니다. 각 부품은 150 mm 인쇄 공간 이내입니다.
재료·프린터 강도는 실물 확인이 필요합니다. 같은 이름의 STEP/F3D는 편집·확인용이며 STL 대신 인쇄하지 않습니다.

- 실리콘 발 위치: [왼쪽](MODELS/kc2_left_silicone_foot_layout.svg) / [오른쪽](MODELS/kc2_right_silicone_foot_layout.svg)
- 하판 조각당 Ø8 mm 접착면 4곳, 총 12곳입니다. 뒤집어 볼 때 CAD XY 좌우 반전에 주의하세요.
- 선택용 링: [MX](MODELS/adapters/kc2_mx_ring_cap_020.stl) / [Choc V1](MODELS/adapters/kc2_v1_ring_cap_020.stl)
- 링은 필요한 키마다 하나입니다. 테두리가 베드 쪽, 첫 층과 이후 층 모두 0.20 mm입니다. 테두리만 한 층이고 전체 높이 1.40 mm는 7층입니다.

## 조립 주의사항

PCB는 하판 밖에서 납땜합니다. 하부 실제 핀·납땜 돌출은 PCB 아랫면에서 최대 2.90 mm 이내인지 확인하세요.
명목 나사는 M1.4×7.50 mm, 왼쪽 8개·오른쪽 9개입니다. 바닥이 추가됐다고 긴 나사로 바꾸지 않습니다.
스위치 핀을 억지로 밀거나 깎지 말고, 소켓 접점에 납이 들어가지 않게 하세요.
Choc 소켓과 MX hat 소켓은 같은 키에 동시에 실장하지 않습니다. MX 상판은 Choc용 유지 보강판이 아닙니다.
전원 전 극성·단락·POWER/RESET을 확인하세요. 접점 공차·인쇄 강도·접착·충전 온도·무선 검증은 수령 후 별도입니다.

## 기존 도구와 검증

기존 경로는 로컬 디렉토리 연결입니다. Windows는 junction, 다른 OS는 symlink를 사용합니다.
파일을 복제하지 않으며 기존 도구의 입출력도 `hardware/PCB`, `hardware/GERBER`, `hardware/MODELS`의 같은 원본에 도달합니다.
새 clone/다른 PC에서는 저장소 루트에서 다음을 실행하세요. 충돌하는 실제 폴더가 있으면 덮어쓰지 않고 중단합니다.

```powershell
python -B -m tools.kc2_current_layout          # 변경 없는 사전 확인
python -B -m tools.kc2_current_layout --apply  # 호환 연결 복원
python -B -m unittest tools.test_kc2_current_layout -v
python -B -m tools.prepare_kc2_first_order --verify-package hardware/GERBER
```

마지막 검증은 기존 도구의 의존성이 설치된 Python 환경에서 실행합니다.
주문 당시 [order.md](../order.md)와 r4 manifest 내부의 이전 논리 경로는 감사용으로 그대로 보존했습니다.
그 문서의 오래된 경로도 연결 복원 후 같은 원본을 가리킵니다. 현재 탐색의 시작점은 이 문서입니다.
모델 폴더 내 기존 `백업`, PCB의 로컬 백업·에디터 기록은 현재 사용 파일이 아니며 이름을 바꾸거나 삭제하지 않았습니다.
