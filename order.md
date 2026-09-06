# KC2 디렉토리·PCB 주문·3D 인쇄 안내

기준일: 2026-09-07. 요구사항 원본은 [SRS](docs/spec/00.index.md)입니다.
이 문서는 `OPS-ARCH-006/007`, `CON-ARCH-004/006`의 파일 위치와 절차를 설명하며 요구사항을 대체하지 않습니다.

> 바닥 일체형 r4의 디지털 설계·출력 검증을 완료했습니다. 아래 r4 패키지와 현재 STL을 사용하세요.
> 주문·결제는 실행하지 않습니다. 실물 접점·출력물 강도·배터리·무선 합격은 별도입니다.

## 1. 현재 디렉토리 구조

주요 디렉토리와 용도입니다. 개별 자동 백업과 전체 테스트 파일은 생략했습니다.

```text
kc2/
├─ order.md                         ← 주문·인쇄 파일 선택 안내
├─ README.md                        ← 프로젝트 진입점
├─ AGENTS.md                        ← SRS·하드웨어 검증 작업 규칙
├─ .gitattributes                   ← 검증 자료의 Git 원본 바이트 보존
├─ .gitignore                       ← 임시·백업·로컬 출력 제외
├─ requirements-cad.txt             ← CAD 도구 의존성
├─ docs/
│  ├─ spec/                         ← 유일한 요구사항 원본·검증 근거 연결
│  ├─ rule/                         ← SRS 작성 규칙
│  ├─ analysis/                     ← 요구사항별 분석·변경 이력
│  ├─ research/                     ← 부품 도면·제조 공차 조사
│  ├─ reports/                      ← DRC/회로/CAD/테스트/출력 검토 결과
│  └─ momory/                       ← 기존 기록(현재 이름 그대로)
├─ hardware/
│  ├─ case/                         ← 현재 하우징 STEP/STL/F3D·검증 manifest
│  │  ├─ adapters/                  ← V1/MX 중앙 링 STL
│  │  └─ 백업/                      ← 기존 보관 자료; 현재 인쇄 원본 아님
│  └─ kicad/
│     ├─ kc2_left/                  ← 정식 왼쪽 PCB 프로젝트
│     ├─ kc2_right/                 ← 정식 오른쪽 PCB 프로젝트
│     ├─ autoroute/                 ← 배선 데이터·현재 replay snapshot
│     ├─ first_order/               ← 버전별 봉인 제조 ZIP
│     │  ├─ solid-floor-20260907-r4/ ← 현재: 바닥 일체형 개정용 패키지
│     │  ├─ v1-recess-20260906-r3/   ← 이전 매립 나사/개방 하판 이력
│     │  ├─ mx-receptacle-20260906-r2/
│     │  └─ mx-receptacle-20260906/  ← 이전 검토 이력
│     ├─ fabrication_review/        ← 실제 거버·드릴 원본과 시각 검토 그림
│     ├─ fabrication/               ← 이전 기본 제조 출력; 현재 주문에 사용 금지
│     ├─ mechanical/                ← 이전 기계 출력; 최신 1:1은 case/ 참조
│     ├─ renders/                   ← 배치·조립 렌더
│     ├─ coupon/                    ← 시험용 PCB; 제품 대신 주문하지 않음
│     ├─ draft/                     ← 비활성 과거 설계·로컬 편집 잔여물
│     ├─ kc2_left-hotswap/           ← 과거 설계
│     └─ backups/, autoroute_*/     ← 로컬 백업·실험 출력
├─ firmware/
│  ├─ kc2_zmk/                      ← ZMK 실드·키맵·설정
│  ├─ out/                          ← 검증에 연결된 좌우 UF2
│  └─ build/                        ← 로컬 빌드 캐시; 커밋 대상 아님
├─ third_party/
│  ├─ kc2.pretty/                   ← 프로젝트 소유 KiCad 풋프린트
│  ├─ kc2.3dshapes/                 ← 부품 3D 모델
│  └─ key-switches.pretty/          ← 외부 스위치 풋프린트 자료
├─ tools/                           ← 생성·검증·테스트 스크립트
│  ├─ fusion/KC2StepToF3D/          ← Fusion native 저장·재열기 도구
│  └─ cache/, __pycache__/          ← 로컬 도구·캐시
├─ kiwi/                            ← 기존 작업 상태 자료; SRS를 대체하지 않음
└─ .codex-tmp/, tmp*/               ← 로컬 실험·복구 자료; 주문/인쇄 사용 금지
```

정식 설계는 `hardware/kicad/kc2_left`, `kc2_right`, `hardware/case`에 있습니다.
`draft`나 백업에서 비슷한 이름의 파일을 골라 쓰지 마세요. 과거 정식 설계는 Git 이력으로,
봉인된 이전 발주 ZIP은 해당 개정의 검토 이력으로 보존합니다.

## 2. 주문할 PCB 거버 ZIP

아래 두 ZIP을 제조 사이트에 각각 업로드합니다. 파일을 변경했다면 먼저 6절의 패키지 검증을 다시 실행하세요.
아래 r4 패키지의 두 ZIP을 사용하며, 기존 r3 ZIP으로 대신 발주하지 마세요.

| 대상 | 정확한 파일 경로 | 한 키보드에 필요한 PCB |
|---|---|---:|
| 왼쪽 | [kc2_left-pcb-fabrication-only.zip](hardware/kicad/first_order/solid-floor-20260907-r4/kc2_left-pcb-fabrication-only.zip) | 1장 |
| 오른쪽 | [kc2_right-pcb-fabrication-only.zip](hardware/kicad/first_order/solid-floor-20260907-r4/kc2_right-pcb-fabrication-only.zip) | 1장 |

좌우는 서로 다른 PCB입니다. 주문 수량은 제조사의 허용 단위에 맞추되 한쪽만 주문하지 마세요.
ZIP을 다시 압축하거나 내부 파일을 추가·수정하지 마세요. 각각 거버9개, job1개,
PTH/NPTH 드릴2개, 드릴 맵2개, 드릴 보고서1개로 총15개 파일입니다.

| 제조 항목 | 설정·확인할 내용 |
|---|---|
| 주문 종류 | Bare PCB 제조만. PCBA 자동 실장 주문 아님 |
| 층수·재질 | 2층, FR-4 |
| PCB 두께 | 1.60 mm |
| 외층 구리 | 1 oz |
| 표면 처리 | ENIG |
| 마스크·실크 | 초록 솔더마스크, 흰 실크 |
| 구멍 | NPTH는 비도금. PTH/NPTH를 임의 합치지 않음 |
| V1 측면 구멍 | Ø2.60 mm. 분석 조건: 직경±0.08 mm, 위치±0.05 mm |
| 비아 | 개별 비아 마스크 덮임. 동일 넷 패드와 겹치는3곳은 노출 예외 |

최종 기준은 [fabrication-profile.json](hardware/kicad/first_order/solid-floor-20260907-r4/fabrication-profile.json)입니다.
업로드 후 자동 인식된 크기·층수·두께·드릴을 미리보기에서 확인하세요. 제조사가 다른 공차를 적용하면
기존 간섭 계산을 그대로 적용하지 마세요. job의 finish 표기는 실제 주문 표면 처리 선택을 대신하지 않습니다.

[왼쪽 수동 조립 BOM](hardware/kicad/first_order/solid-floor-20260907-r4/kc2_left-manual-mx-bom.json) /
[오른쪽 BOM](hardware/kicad/first_order/solid-floor-20260907-r4/kc2_right-manual-mx-bom.json)은 부품 확인용입니다.
BOM/CPL 자동 실장 업로드 승인이 아닙니다.

`fabrication_review/v1-recess-20260906-r3/{left,right}`에는 변경되지 않은 PCB의 검토 거버 원본이 있습니다.
바닥 변경은 PCB 배선을 바꾸지 않으므로 재검증한 같은 제조 바이트를 사용합니다.
이전 하우징 검증까지 그대로 유효하다는 뜻은 아닙니다.

## 3. 인쇄할 하우징 STL — 선택한 MX 조립 기준

최종 r4 검증 완료 후 아래 **6개 STL을 각각1개** 인쇄합니다. `.step`과 `.f3d`는 CAD 확인·편집용입니다.
정식 경로의 파일명은 이전 개정과 같으므로, 파일이 존재한다는 이유만으로 바닥 개정 검증이 끝났다고 판단하지 마세요.

| 용도 | 인쇄 파일 | 수량 |
|---|---|---:|
| 왼쪽 바닥 일체형 하판 | [kc2_left_lower_housing.stl](hardware/case/kc2_left_lower_housing.stl) | 1 |
| 오른쪽 하판 A | [kc2_right_lower_housing_part_a.stl](hardware/case/kc2_right_lower_housing_part_a.stl) | 1 |
| 오른쪽 하판 B | [kc2_right_lower_housing_part_b.stl](hardware/case/kc2_right_lower_housing_part_b.stl) | 1 |
| 왼쪽 MX 보강판 뚜껑 | [kc2_left_mx_upper_housing.stl](hardware/case/kc2_left_mx_upper_housing.stl) | 1 |
| 오른쪽 MX 뚜껑 A | [kc2_right_mx_upper_housing_part_a.stl](hardware/case/kc2_right_mx_upper_housing_part_a.stl) | 1 |
| 오른쪽 MX 뚜껑 B | [kc2_right_mx_upper_housing_part_b.stl](hardware/case/kc2_right_mx_upper_housing_part_b.stl) | 1 |

단위 mm, 축척100%로 사용하며 각 조각은150×150×150 mm 이내입니다. 자동 크기 맞춤으로 축소하지 마세요.
특정 재료·프린터 프로파일의 강도와 치수 정확도는 아직 검증되지 않았습니다.

- **하판:** 넓고 평평한 새 바닥 외면이 베드에 닿게 둡니다. 첫 층과 이후 층이 모두0.20 mm이면 바닥1.20 mm는6층 높이입니다. 바닥층0 또는 vase/spiral 설정은 사용하지 마세요. 미리보기에서 바닥 전체와 작은 받침·파일럿이 생존하는지 확인합니다.
- **MX 뚜껑:** 보강판의 평평한 윗면을 베드에 놓고 받침 기둥이 위로 향하게 뒤집습니다.14 mm 개구, 나사 포켓과 얇은 벽을 확인합니다. 매립 포켓 위 작은 브리지 품질은 실물 확인이 필요합니다.
- 오른쪽 A/B는 별도 조각입니다. 하판과 상판의 결합부를 바꿔 끼우지 않습니다. 출력 오차를 나사로 끌어당겨 억지로 맞추지 마세요.
- 내부 여유 공간을 서포트 잔재로 막지 마세요. 바닥이 있으므로 조립 후 아래에서 납땜하지 않습니다.

### 실리콘 미끄럼방지 발

[왼쪽 부착 배치도](hardware/case/kc2_left_silicone_foot_layout.svg)와
[오른쪽 부착 배치도](hardware/case/kc2_right_silicone_foot_layout.svg)에 부착 위치를 표시합니다.
하판 조각마다 Ø8 mm 평면 영역4곳, 총12곳이며 분할선·가장자리를 피합니다.
이는 부착 공간의 치수이지 특정 제품의 접착력·마찰 성능 검증은 아닙니다.
배치도는 CAD의 XY 좌표 기준입니다. 하판을 뒤집어 바닥에서 보면 좌우가 반전될 수 있으므로, 분할선과 외곽 모양을 기준으로 위치를 맞추세요.
발을 같은 높이로 맞추고 깨끗하고 평평한 면에 붙여 책상에서 흔들림이 없는지 확인하세요.
오른쪽 각 인쇄 조각에도 지지가 있어야 합니다.

## 4. 선택해서 인쇄할 중앙 링

| 모드 | 파일 | 사용 수량 |
|---|---|---|
| MX | [kc2_mx_ring_cap_020.stl](hardware/case/adapters/kc2_mx_ring_cap_020.stl) | 적용할 키마다1개, 최대70개 |
| Choc V1 | [kc2_v1_ring_cap_020.stl](hardware/case/adapters/kc2_v1_ring_cap_020.stl) | 적용할 키마다1개, 최대70개 |

두 링을 한 키에 겹치지 마세요. 소량으로 중심 기둥·안착을 확인한 뒤 필요한 수량을 인쇄합니다.
**넓은 테두리가 베드 쪽**입니다. 첫 층과 이후 층 모두0.20 mm로 설정하면 테두리는 첫1층,
전체1.40 mm 링은7층입니다. 조립할 때는 뒤집어 테두리를 PCB 위에 둡니다.
내경 V1 3.50/MX 4.10 mm는 초기 맞춤값입니다. 출력 수축·실물 공차는 별도 확인하며,
특히 MX 벽0.35 mm가 슬라이서에서 사라지지 않는지 확인하세요.

Choc V1은 하부 Choc 소켓+V1 링 대체 모드이며 MX 뚜껑을 Choc 유지용 보강판으로 취급하지 않습니다.
Choc V2도 별도의 하부 소켓 조립 모드입니다. 한 키에 Choc 소켓과 MX hat 소켓을 동시에 실장하지 않습니다.
선택한 MX 모드의 hat 소켓은70키에140개이며 명목 길이3.00/몸통Ø1.45/플랜지Ø2.00×0.20 mm입니다.
내부 접점 수용 범위·삽입력·공차는 미공개입니다. 핀을 깎거나 힘으로 눌러 맞추지 마세요.

## 5. 조립 순서와 나사

1. PCB 좌우, nice!nano USB 방향, 배터리 BAT+/GND, POWER/RESET 및 다이오드 cathode 표시를 확인합니다.
2. **하판 밖에서** PCB를 납땜합니다. 스위치·보강판으로 소켓을 정렬해 가접하고 식힌 뒤 탈착을 확인한 후 마무리합니다. 열린 소켓 내부로 납을 흘리지 마세요.
3. PCB 아래 핀·납땜 돌출을 측정합니다. 바닥 여유의 설계 조건은 PCB 아랫면 기준 최대2.90 mm입니다. 절단 가능한 납땜 리드는 정리하되 스위치 자체 핀/돌기는 임의 절삭하지 않습니다. 접점 깊이가 부족하면 조립을 중단합니다.
4. 오른쪽 하판 A/B를 결합하고 PCB를 받침에 올립니다. 눌러야 안착한다면 간섭 원인을 먼저 찾습니다.
5. MX 뚜껑·스위치를 맞추고 나사를 조입니다. 왼쪽8개/오른쪽9개, **M1.4×7.50 mm가 명목 길이**이며 이전9 mm는 사용하지 않습니다.
6. 나사 머리 최대 모델Ø3.00×1.20 mm, 포켓Ø3.40×깊이1.50 mm입니다. 새 바닥 때문에 나사를 길게 바꾸지 마세요. 명목 파일럿 삽입2.20 mm/끝 여유0.60 mm이며 실물 길이·출력 공차를 확인합니다.
7. 지정 평면에 실리콘 발을 붙이고 흔들림·분할부·키캡 전체 행정을 확인합니다.
8. **전원 인가 전** 배터리 극성·단락·POWER/RESET을 확인합니다. 미확인 배터리에 charge boost를 켜지 않습니다. 이후70키 입력·충전·무선 성능을 검사합니다.

하판 외면 Z-2.20, PCB 아래/위 Z2.50/4.10, 보강판 위 Z9.30 mm입니다.
실리콘 발을 제외한 바닥 외면–보강판 위 높이는11.50 mm이며 스위치·키캡 높이는 포함하지 않습니다.
나사 머리는 보강판 위보다0.30 mm 낮고, 접착 발 높이만큼 책상 위 높이가 더해집니다.

## 6. 검증·재현·Git 보존

```powershell
& C:/Python312/python.exe -B -m tools.prepare_kc2_first_order --verify-package hardware/kicad/first_order/solid-floor-20260907-r4
```

현재 소스·보고서·CAD·거버 바이트가 모두 필요한 검증이며 실물 합격 판정이 아닙니다.
도구 경로는 환경에 맞추되 PCB 분석은 KiCad Python, CAD는 CadQuery/Shapely가 있는 Python을 사용합니다.
`.gitattributes`가 봉인 해시를 Windows 줄바꿈 변환으로부터 보호합니다. 설계·검증 입력을 편집하면
manifest 해시를 수동으로 고치지 말고 검증·릴리스를 새로 만드세요.
임시·에디터 기록·개인 상태는 커밋에서 제외하고, 추적된 과거 자료는 임의 삭제하지 않습니다.
검증된 좌우 UF2는 재현에 필요한 예외로 포함하되 전체 ZMK 빌드 캐시는 업로드하지 않습니다.
