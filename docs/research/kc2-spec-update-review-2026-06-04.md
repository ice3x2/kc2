# KC2 Spec Update Review - 2026-06-04

## 목적

사용자 결정 사항을 KC2 스펙에 반영하기 전에 5개 서브에이전트로 분리 검토했다.

- KC2 명명 통일과 KC1 계승 관계
- nice!nano v2 컨트롤러 방향, USB-C 방향, 안테나 keepout
- 결합 edge와 PCB 외곽 테두리 치수
- 배터리와 nice!nano `B+`/`B-` 직접 케이블 납땜 구조
- DO-35 1N4148 유지와 SMD diode 전환 가능성

## 최종 결정

### KC2 명명

KC2는 KC1의 단순 PCB 변환본이 아니라 KC1의 배열 철학과 결합/분리 사용성을 계승한 2세대 PCB 설계로 정의한다.

- 문서명: `KC2 Keyboard Specification`
- 하드웨어 프로젝트명: `KC2`
- ZMK shield id: `kc2`
- ZMK shield siblings: `kc2_left`, `kc2_right`
- 기존 `kc1` 식별자는 KC1/이전 설계 기록으로만 남긴다.

### 컨트롤러 방향

nice!nano v2는 각 half의 숫자열 바로 위 둥근 돌출 탭에 가로 배치한다.

- 왼쪽 half: USB-C는 왼쪽 바깥쪽, antenna end는 오른쪽 결합 edge 쪽
- 오른쪽 half: USB-C는 오른쪽 바깥쪽, antenna end는 왼쪽 결합 edge 쪽
- 좌우 모두 top-side socket 배치로 두고, 단순 mirror가 아니라 회전 방향만 다르게 잡는다.
- KiCad에는 `USB_OUT_LEFT`, `USB_OUT_RIGHT`, `ANTENNA_INWARD` 표시를 넣는다.

USB-C를 바깥쪽으로 향하게 하면 antenna end가 중앙 결합 edge 쪽을 향한다. 이것은 설계 모순이 아니라 keepout으로 관리할 RF/기구 조건이다.

### Programming Tact Switch

USB-C 포트 아래쪽은 각 half의 key-side, 즉 숫자열을 향한 쪽으로 정의한다.

- tact switch는 상면 배치한다.
- `RST`와 `GND` 사이에 연결한다.
- 1:1 출력물로 손가락 접근성과 USB 케이블 간섭을 확인한다.

### Antenna Keepout

1차 PCB 초안 기준 keepout은 다음과 같이 둔다.

- antenna end에서 최소 10 mm 길이
- nice!nano 폭 전체
- 인접 결합 edge 방향 포함
- 금지 항목: copper pour, trace, via, battery, wire strain relief, M2 screw, 금속 insert, 금속 보강물

공식 pinout/schematic과 실물 측정 후 조정할 수 있지만, 초안에서는 10 mm를 기본값으로 둔다.

### PCB 외곽과 결합 Edge

서브에이전트 검토 결과, 결합 edge 기준값은 2.8 mm로 결정했다.

- 일반 PCB 외곽 테두리: 5.5 mm 기준, 5.0-6.0 mm 허용
- 결합 edge: 2.8 mm 기준, 2.5-3.0 mm 허용
- 결합 edge 절대 하한: 2.5 mm
- 일반 edge-to-copper clearance: 1.0 mm 이상
- 결합 edge-to-copper clearance: 최소 0.8 mm, 가능하면 1.0 mm

2.0-2.3 mm는 반복 결합/분리와 라우팅 공차에 대한 여유가 작다. 3.0 mm는 안전하지만 compact 요구와 약간 충돌한다. 따라서 2.8 mm가 제작성과 사용감 사이의 균형점이다.

M2 고정 조건:

- M2 고정 홀: NPTH 2.2 mm 기본
- screw head / 3D printed boss keepout: 지름 5.0 mm 이상
- M2 홀 중심과 PCB 외곽 거리: 최소 4.0 mm, 가능하면 4.5 mm 이상
- 결합 edge의 얇은 구간에는 M2 홀을 두지 않는다.
- 결합 edge는 하부 바닥판의 연속 lip/rib로 보강한다.

### 전원 연결 구조

이전 A2506 connector 2개 구조는 KC2에서 폐기한다.

- 배터리 lead는 PCB `BAT+`/`BAT-` solder pad에 직접 납땜한다.
- nice!nano `B+`/`B-` top pad에는 유연한 stranded wire를 직접 납땜한다.
- 해당 wire의 반대쪽은 PCB `NN_B+`/`NN_B-` pad에 납땜한다.
- `BAT+`와 `NN_B+`, `BAT-`와 `NN_B-`는 짧고 넓은 trace로 연결한다.
- 전원 lead에는 strain relief hole, wire loop, 접착 고정, 하부 바닥판 케이블 고정 구조를 둔다.
- socketed nice!nano는 24핀 socket에서 뺄 수 있지만, `B+`/`B-` wire를 desolder하지 않으면 완전 분리는 불가능하다.
- slide switch와 전원 connector가 없으므로 일반 사용 중 hard power-off는 제공하지 않는다.
- 정비 시 전원 차단은 `BAT+` service pad desolder 또는 optional solder jumper 개방으로 처리한다.

### Diode

기본 시도는 사용자가 지정한 through-hole `1N4148` SOD-27(DO-35)이다. 다만 KC2의 compact outline, 71개 diode, 다중 호환 switch footprint, M2 홀 조건을 동시에 만족하지 못할 수 있다.

전환 순서:

1. `1N4148` SOD-27/DO-35 through-hole
2. `1N4148W` / SOD-123
3. `1N4148WS` / SOD-323

SOD-123은 손납땜성과 공간 절약의 균형이 좋다. SOD-323은 더 작지만 71개 수동 납땜 난도가 높으므로 SOD-123으로도 outline, M2 hole, routing이 성립하지 않을 때 사용한다.

DO-35 유지 실패 기준:

- switch/stabilizer footprint와 courtyard overlap
- M2 hole 배치 실패
- hole-to-hole clearance 위반
- 결합 edge 2.5-3.0 mm 여백 침범
- 하부 바닥판 지지점 간섭
- lead bending 공간 부족

## 확인한 자료

- nice!nano 제품 페이지: https://nicekeyboards.com/nice-nano/
  - Pro Micro drop-in replacement, mid-mount USB-C, 3.2 mm thickness, nRF52840, charger spec 확인
- nice!nano getting started: https://nicekeyboards.com/docs/nice-nano/getting-started/
  - `B+`/`B-`에 socket/header를 설치하지 말 것, battery soldering polarity, RST/GND bootloader 진입 확인
- nice!nano pinout/schematic: https://nicekeyboards.com/docs/nice-nano/pinout-schematic/
  - USB-C, B+/B-, RST/GND, pinout 기준 확인
- nice!nano FAQ: https://nicekeyboards.com/docs/nice-nano/faq/
  - split half별 개별 Li-Po 사용, USB-C charging 확인
- KiCad board edge clearance DRC: https://docs.kicad.org/master/en/pcbnew/pcbnew.html
  - board edge clearance가 DRC 대상으로 다뤄지는 점 확인
- Vishay 1N4148 DO-35 datasheet: https://www.digikey.com/en/htmldatasheets/production/1227458/0/0/2/1n4148
  - DO-35 package, axial leaded package 치수와 전기 특성 확인
- Vishay 1N4148WS SOD-323 datasheet: https://www.vishay.com/docs/86455/1n4148ws.pdf
  - SOD-323 package와 footprint recommendation 확인
- MCC 1N4148W SOD-123 datasheet: https://www.mouser.com/datasheet/3/225/1/1N4148W%28SOD-123%29.pdf
  - SOD-123 package 치수와 전기 특성 확인
- DeviceMart 1N4148W SOD-123 후보: https://www.devicemart.co.kr/goods/view?no=14592018
- DeviceMart 1N4148WS SOD-323 후보: https://www.devicemart.co.kr/goods/view?no=15106773

## 스펙 반영 파일

- `docs/spec.md`
