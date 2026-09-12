# 내부 충전형 보강판 개발 기록

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.
상태: 디지털 구현·실제 형상 검증·최종 게시 완료. 현재 `hardware/MODELS`에는 MX, Choc V1, Deep Sea Mini의 내부 충전형 상판이 게시되어 있습니다. 실물 출력·부품 편차·체결 강도 검증은 별도입니다.

현재 파일 선택은 [인쇄·조립 안내](../../../hardware/MODELS/PRINT-filled-plates.md)를 따릅니다. [게시 manifest](../../../hardware/MODELS/kc2_filled_plate_manifest.json)는 상판 21개 파일과 보존한 하판 14개·PCB/거버 16개를 포함한 124개 바이트 바인딩을 검사합니다. 이전 보강 MX 상판은 Git `d9d3729`에 보존했고, 이전 manifest는 `previous-local-cover-manifest.json`에 기록으로 옮겼습니다.

`final-tests.json`의 47개 회귀시험, 여섯 원본 STEP 전체 단면, 아홉 STL 및 독립 설계 계약, 여섯 실제 Fusion 저장·재열기·읽기 결과의 전체 단면, 하판 포함 좌우 조립 검사가 통과했습니다. 각 종류/좌우의 `*-sectional-progress.json`은 원본 STEP 검사, `*-native-review.json`은 실제 재열기 형상 검사입니다. 원본 STEP과의 단면 검사는 독립 계약 및 STL 검사와 함께 사용하며 단독으로 전체 검증을 주장하지 않습니다.

`portable-verification.json`은 게시 파일만 새 임시 디렉토리에 복사한 후 `python -S`로 사이트 패키지 없이 검증한 실행 기록입니다. 정상 검증·복원 검증이 통과했고, STL 변조·출력 목록 누락·Deep Sea native 증거 누락 세 경우를 모두 거부했습니다. 임시 CAD 작업 경로는 보고서의 원래 관측 위치이며 게시 검증기는 이를 실제 저장소 파일에 대응시킵니다.

목표는 Choc V1, 선택된 저상형 Kailh Deep Sea 갈축, MX 세 종류 모두의 구조 공간을 실제 CAD 솔리드로 채우는 것입니다. 벽만 두껍게 하거나 슬라이서 인필 설정만 바꾸는 결과로 대체하지 않습니다. 스위치/클립, 나사 통과 홀·머리 포켓, PCB 비접촉 여유 및 컨트롤러/서비스 공간은 보호합니다.

## 현재 구현

`tools/kc2_solid_plate.py`는 보호 공간의 높이 경계마다 전체 단면을 채웁니다. `tools/kc2_filled_plate_profiles.py`는 세 조립 높이를 구분합니다. `tools/generate_kc2_filled_plates.py`는 실제 PCB 좌표를 읽어 `.codex-tmp/solid-filled-plates`에 생성합니다. 임시 출력은 최종 인쇄 승인 파일이 아닙니다.

실패 우선 테스트로 빈 내부를 남긴 벽-only 결과, 나사홀 충전, 맞지 않는 높이, 분할 틈 충전을 거부했습니다. 실제 좌표 검사에서 기존 A/B 맞물림 홈이 채워지는 문제가 검출되어 반대편 돌기의 여유를 추가로 보호했습니다. 단면 검사기는 실제 BRep의 모든 면이 수직/수평 평면이고 모든 꼭짓점 높이가 예상 경계임을 먼저 확인합니다. 그 뒤 각 높이 구간 단면 전체와 요구 영역을 비교하므로, 단순 체적 일치만으로 통과시키지 않습니다. 숨은 중간 높이 공동과 기울어진 면을 거부하는 변이 시험을 포함합니다.

`tests-progress.json`은 코어·치수·실제 좌표 계획·합성 솔리드 시험 증거입니다. 실제 여섯 전체 보강판의 검토, 출력 메시 검사, Fusion F3D 재열기 및 게시 검증을 대체하지 않습니다.

## 추가 검증 진행

`verifier-tests.json`: 35개 회귀시험 통과. 생성기의 프로파일 표·채움 함수를 호출하지 않는 독립 치수/단면 재계산, 누락된 내부 재료·막힌 나사홀·변경된 분할 마스크·잘못된 높이를 거부하는 시험, 실제 STL 검증기 및 여섯 Fusion 작업 사전검사 시험을 포함합니다. 기존 PCB 좌표 추출기와 기존 서비스/분할 인터페이스는 공유하므로, 부품 실측까지 독립적으로 수행했다는 뜻은 아닙니다.

세 종류 좌우 STEP 6개 및 인쇄 STL 9개가 임시 작업 위치에 생성됐습니다. [실제 메시·독립 설계 검사](mesh-contract-review.json)에서 9개 실제 STL은 모든 표면이 수직/수평이고 꼭짓점 높이가 설계 경계에 있는지 먼저 확인한 뒤, 각 높이 구간의 단면 전체를 독립 설계와 비교하여 모두 통과했습니다. STL 좌표 양자화 허용치는 높이 0.00001 mm, 단면 누락/초과 면적 각각 0.02 mm²이며, 큰 공동이나 나사홀 충전을 허용하는 공차가 아닙니다. 실제 STL에서 측정한 보강판 좌우 최소 간격은 MX 0.445999 mm, V1 및 Deep Sea 1.299999 mm이고 투영 겹침은 0입니다.

[하판 포함 조립 검사](assembly-review.json)도 통과했습니다. 이전 실제 CAD 검증과 바이트가 일치하는 하판의 전체 외곽과 새 STL의 전체 외곽을 합쳐 기존 좌우 위치에서 검사했습니다. MX 최소 0.445999 mm, V1/Deep Sea 최소 1.299998 mm, 투영 겹침 0입니다. 기존 하판 14개 CAD 파일과 주문된 PCB/거버 16개 파일이 그대로임을 함께 확인했습니다. 이 검사에는 실제 부품·키캡의 제조 편차나 조립 하중이 포함되지 않습니다.

`tools/fusion/KC2FilledPlatesToF3D/KC2FilledPlatesToF3D.py`로 여섯 STEP을 실제 Fusion에서 열고 F3D를 저장한 뒤 다시 열어 STEP으로 읽어내는 작업이 모두 통과했습니다. 원본 STEP 여섯 개의 전체 단면 검사와 `tools/review_kc2_filled_native.py`의 독립 계약 대비 native 형상 검사도 모두 통과했습니다. `*.native-readback.step`은 인쇄용 대체 모델이 아니라 F3D 재열기 검증 증거입니다.

## 치수 근거 및 한계

[V1 가족 도면](https://www.kailhswitch.com/Content/upload/pdf/201915927/CPG135001D01_-_Red_Linear_Choc.pdf)의 장착 단면과 기존 0.20 mm 링 테두리를 반영한 공학 모델입니다. 특정 수령 V1 축의 실측값은 아닙니다.

[Kailh 저상형 정음 가족 도면](https://www.kailhswitch.com/uploads/15927/files/CPG1353S01D01-01-data-sheet.pdf?rnd=494)은 임시 선형 모델 도면입니다. 클립 틈 1.35와 하부 0.80에서 판 높이 2.15 mm를 추론했습니다. [Deep Sea Mini 판매 페이지](https://kailhswitch.net/products/kailh-deep-sea-silent-min-low-profile-keyboard-switch)의 Whale 선택과 이전 갈축 로트를 이 도면과 동일한 제어 도면으로 확정한 것은 아닙니다. 정상 높이 Deep Sea Box와 혼동하지 않습니다.

| 설계값, mm | MX | Choc V1 + 링 | Deep Sea Mini 가족 기준 |
|---|---:|---:|---:|
| 판 아래 Z | 7.80 | 5.30 | 5.05 |
| 판 위 Z | 9.30 | 6.50 | 6.25 |
| 머리 받침 Z | 7.80 | 5.10 | 5.10 |
| 보스 상단 Z | 9.30 | 6.60 | 6.60 |
| 명목 나사 길이 | 7.50 | 5.00 | 5.00 |

저상형 보스는 판보다 조금 높습니다. 실제 키캡 내부·전체 이동·체결 강도는 미검증이며, 기존 MX 나사를 저상형에 사용하지 않습니다. PCB/거버와 하판 두 옵션은 변경하지 않았습니다. 디지털 납품 목표가 완료되어도 이런 실물 검증이 자동으로 통과되는 것은 아닙니다.
