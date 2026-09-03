# KC2 X3 V2 JLCPCB 주문 전 종합 감사 보고서

> 작성일: 2026-09-02  
> 활성 대상: `kc2-x3-v2`  
> 요구사항: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`, `REL-ARCH-001`, `OPS-ARCH-006`

## 최종 개선 업데이트

> 이 절이 현재 상태의 최종 판정이다. 아래의 최초 감사 내용은 수정 전 결함과
> 개선 근거를 보존한 기록이며, “17개 support 교차”, stale ZIP·render·firmware
> metadata 지적은 모두 해결된 과거 finding이다.

### 현재 판정

- `OPS-ARCH-006` 정본 승격: **완료**
  - left: `hardware/kicad/kc2_left/kc2_left.kicad_pcb`
  - right: `hardware/kicad/kc2_right/kc2_right.kicad_pcb`
  - active `hardware/kicad/draft/x3-v2` 및 `hardware/case/draft/x3-v2`: 없음
  - 다른 historical draft variant: 변경 없음; 이전 정본은 Git 이력으로 보존
- 배열 구조: **무보강판·무스테빌라이저** (`STAB*` 좌우 각 0개)
- 디지털 PCB·DRC·Gerber/Excellon/제조 산출물 검증·기계·하우징·render·firmware:
  **PASS**
- 아래 SHA-256과 정확히 일치하는 좌·우 bare-PCB 및 시험 coupon ZIP:
  **JLCPCB 업로드·시제품 제작 가능**
- 양산 수량 PCB·PCBA·일반 부품 조달: **ORDER BLOCKED**
- PCBA reference BOM/CPL 업로드: **금지**

해결된 항목:

- key-load support와 B.Cu/via 교차 제거
  - left/right B.Cu 최소 여유 `0.3500 mm`, 기준 `0.3000 mm`
  - via 최소 여유 left `1.2433 mm`, right `0.4947 mm`
  - support collision `0`
- deterministic route 재생 및 연결성 검증
  - left `616` / `b37c88d783baa27e6358d1c3baf33528d282934c41c507f2da5edc44e739ebbb`
  - right `803` / `44a0c7fdd446f3153d2faf2506194947577b74147713c9a097c7ac83a9c1a964`
- fresh KiCad DRC: 좌우 `error=0`, `warning=0`, `unconnected=0`
- Gerber/Excellon/BOM/ZIP, 1:1 mechanical, STEP/STL, render 전체 재생성 및
  source/hash 재결속
- 우측 PTH `0.300 mm` drill count를 실제 via `53`개와 일치시킴
- firmware metadata를 실제 `J_BAT1 → SW_PWR1 → U1 RAW/GND` 계약으로 수정
- fabrication CSV의 LF/CRLF 비교만 정규화하고 의미 변조 거부 테스트 유지

현재 제한 제작용 패키지:

- Left: `hardware/kicad/fabrication/kc2_left_jlcpcb.zip`
  - SHA-256: `ce75086426b963a285fa14bcca3a84d483baf288a3610507c6ee8b5c8e464e8e`
- Right: `hardware/kicad/fabrication/kc2_right_jlcpcb.zip`
  - SHA-256: `db51599eae16657ede44b6fecf33a735a459cff4a932b0f34bcf0e3f71226ef8`
- Coupon: `hardware/kicad/fabrication/kc2_coupon_jlcpcb.zip`
  - SHA-256: `5574b62981e4be7c256ddc987441e3b16c3a05af527a459ccf74cce2d5133c74`

제한 제작 허용은 위에 적은 현재 Left/Right JLCPCB ZIP과 정확한 SHA-256에만
적용된다. PCB source 또는 패키지가 하나라도 변경되면 이 허용은 즉시 무효이며,
재생성·재검증·새 해시 결속 없이는 제작할 수 없다.

주요 잔여 차단 요인은 다음 물리·조달·SSOT gate다.

1. 정확한 protected 301230 pack/lead, controller stack, strain-relief,
   POWER/RESET service
2. 정확한 Kailh Deep Sea low-profile switch MPN과 controlled drawing, 그리고
   IMMS 전원 스위치의 정확한 제조사/MPN·controlled drawing 또는 footprint와
   핀 기능·치수·방향·continuity를 확인한 incoming inspection
3. populated coupon/first article의 Choc/MX/diode fit과 3.0/3.3 V matrix scan
4. 정확한 M1.4 screw/driver, torque/repeat/full-pattern, keycap-skirt, 2 N
   deflection
5. power-transition oscilloscope와 최종 enclosure BLE RSSI/PER/disconnect
6. 검증을 통과한 SRS-sync mutation의 사용자 적용 gate 완료

`physical_evidence.status=pending_physical_evidence`와 `order_ready=false`는
네 물리 evidence bundle이 실제 측정으로 채워질 때까지 유지한다. 최종 생산
PCB·PCBA·일반 부품 주문은 위 조달·SSOT gate까지 모두 닫힐 때까지 차단한다.

## 과거 최초 감사 기록 — 현재 주문 판정으로 사용하지 않음

> 아래 절은 수정 전 결함을 보존한 historical 기록이다. 당시의 Gerber/ZIP
> 업로드 금지 판정은 폐기됐다. 현재 주문 판단에는 문서 맨 위의
> `최종 개선 업데이트`와 거기에 결속된 세 ZIP/SHA-256만 사용한다.

### [폐기된 당시 판정] 수정 전 Gerber/ZIP은 업로드 금지였음

좌우 PCB의 DRC, 실제 패드 네트, 행렬 연결, nice!nano 방향, diode 극성,
Gerber/Excellon 기본 구조는 디지털 검사를 통과했다. 그러나 다음 주문 차단
문제가 남아 있다.

1. 17개 키별 하부 지지대가 B.Cu 배선 위 솔더마스크를 반복 하중
   접촉면으로 사용한다.
2. 물리 검증 4개 번들이 모두 비어 있고 `order_ready=false`이다.
3. 정확한 배터리·전원 스위치·switch/socket·M1.4 나사/드라이버 사양과
   실물 적합성이 확정되지 않았다.
4. fabrication verifier와 render verifier가 현재 실패한다.
5. 펌웨어 조립 메타데이터가 실제 PCB 전원 회로와 모순된다.

현재 좌우 JLCPCB ZIP의 Gerber/드릴 바이트는 source/hash와 맞지만, 아래
문제를 해결하면 PCB 또는 하우징/라우팅이 바뀌므로 반드시 모두 새로
생성해야 한다.

## 용어 확인

저장소의 설계 계약은 **무보강판(plateless), 무스테빌라이저** 키보드다.
문자 그대로 “타공이 없는 PCB”는 아니다.

- switch용 기계 NPTH가 존재한다.
- M1.4 고정 NPTH는 왼쪽 8개, 오른쪽 9개다.
- 배터리 strain-relief NPTH와 각 switch의 locator hole도 존재한다.

사용자가 말한 “무타공판”이 “무보강판”을 뜻한다면 현재 방향과 일치한다.
실제로 모든 구멍이 없는 PCB를 뜻한다면 현 설계와 정면으로 충돌하므로
PCB를 다시 설계해야 한다.

## CRITICAL — 주문 전 반드시 해결

### 1. 키별 하중 지지대와 B.Cu 배선이 겹친다

`2.40 mm` 직경의 zero-gap 하부 지지 디스크를 실제 하우징 좌표에서 PCB
좌표로 변환한 뒤, 활성 B.Cu track capsule과 교차 검사했다.

- 영향받은 지지대: 총 17개
- 교차한 track segment: 총 22개(Left 6개 + Right 16개)
- Left: 31개 중 6개 지지대, 6개 track segment 교차
  - `SW3, SW4, SW5, SW6, SW7, SW11`
- Right: 39개 중 11개 지지대, 16개 track segment 교차
  - `SW2, SW3, SW4, SW5, SW6, SW7, SW11, SW12, SW26, SW27, SW28`
- Via 교차: 0개

| Half / support | Housing center (mm) | PCB center (mm) | 교차 B.Cu net |
|---|---:|---:|---|
| Left `SW3` | `(89.9875, 32.7750)` | `(80.1250, 72.0250)` | `L_ROW0` |
| Left `SW4` | `(70.9375, 32.7750)` | `(99.1750, 72.0250)` | `L_ROW0` |
| Left `SW5` | `(51.8875, 32.7750)` | `(118.2250, 72.0250)` | `L_ROW0` |
| Left `SW6` | `(32.8375, 32.7750)` | `(137.2750, 72.0250)` | `L_ROW0` |
| Left `SW7` | `(13.7875, 32.7750)` | `(156.3250, 72.0250)` | `L_COL6` |
| Left `SW11` | `(61.4125, 51.8250)` | `(108.7000, 91.0750)` | `L_ROW1` |
| Right `SW2` | `(128.0875, 32.7750)` | `(70.6000, 72.0250)` | `R_ROW0` |
| Right `SW3` | `(109.0375, 32.7750)` | `(89.6500, 72.0250)` | `R_ROW0` |
| Right `SW4` | `(89.9875, 32.7750)` | `(108.7000, 72.0250)` | `R_COL3`, `R_ROW0` |
| Right `SW5` | `(70.9375, 32.7750)` | `(127.7500, 72.0250)` | `R_ROW0` |
| Right `SW6` | `(51.8875, 32.7750)` | `(146.8000, 72.0250)` | `R_ROW0` |
| Right `SW7` | `(30.4562, 32.7750)` | `(168.2313, 72.0250)` | `R_ROW0` |
| Right `SW11` | `(118.5625, 51.8250)` | `(80.1250, 91.0750)` | `R_ROW1` |
| Right `SW12` | `(99.5125, 51.8250)` | `(99.1750, 91.0750)` | `R_COL6` |
| Right `SW26` | `(123.3250, 89.9250)` | `(75.3625, 129.1750)` | `R_ROW3` |
| Right `SW27` | `(104.2750, 89.9250)` | `(94.4125, 129.1750)` | `R_ROW3` |
| Right `SW28` | `(85.2250, 89.9250)` | `(113.4625, 129.1750)` | `R_COL3` |

모든 via는 양면 tenting되어 있고 B.Cu도 solder mask로 덮여 있으므로 즉시
노출 구리 단락을 뜻하지는 않는다. 문제는 지지대가 솔더마스크 위 routed
copper를 반복 타건 하중의 마찰·마모면으로 사용한다는 점이다.

`CON-ARCH-006` AC-5/AC-6과 구현 지침은 support가 routed-copper clearance를
보존하고, solder mask over routed copper를 wear surface로 사용하지 않도록
요구한다. 현재 housing verifier는 일반 key-load support를 배치할 때 routed
copper를 금지 geometry에서 빼지 않아 이 결함을 놓친다.

필수 조치:

- 해당 지지점을 component-clear/routed-copper-clear 영역으로 이동하거나
- B.Cu route를 다시 배선하고
- 최소 `0.30 mm` XY 여유를 검증기에 명시적으로 추가한 뒤
- housing, routing, DRC, mechanical, render, fabrication 산출물을 전부 다시
  생성한다.

### 2. 주문 승인용 물리 증거가 없다

`hardware/kicad/kc2_physical_evidence.json`:

- `status=pending_physical_evidence`
- `order_ready=false`
- `source_bindings={}`
- 아래 4개 bundle의 `artifacts`와 `metrics`가 전부 비어 있음

필수 bundle:

1. controller/socket/battery/POWER/RESET 실물 stack·service·pull 검증
2. 3.0 V / 3.3 V 최대 동일 행·열 physical scan
3. housing/fastener/full-pattern/2 N deflection 검증
4. power-transition oscilloscope와 최종 조립 BLE/RSSI/PER/disconnect 검증

V2 release verifier는 `DIGITAL PASS` 후 종료 코드 `2`, `NOT ORDER READY`를
반환했다.

### 3. 정확한 구매 부품과 치수가 아직 확정되지 않았다

| 부품 | 디지털 상태 | 주문 차단 상태 |
|---|---|---|
| Diode | exact Diodes Inc. `1N4148W-13-F`, SOD-123, pad 1 cathode/row 통과 | 실물 coupon scan/Vf pending |
| Choc V2 switch | 70-key footprint geometry 통과 | exact manufacturer MPN/drawing revision, 실물 fit pending |
| Choc socket | `CPG135001S30` class geometry 통과 | 실제 socket 0°/180° 실장·납땜·housing fit pending |
| MX 5-pin | top-side direct-solder geometry 통과 | 실제 switch/핀/키캡/housing fit pending |
| Battery | nominal 301230, 3.7 V/100 mAh | exact MPN, protection, swollen thickness, lead-exit drawing pending |
| J_BAT1 | direct-solder net/marking 통과 | 구매 lead 대비 provisional `0.90 mm` drill 적합성 pending |
| Power switch | IMMS-12V/BSI-10 proxy geometry | exact MPN/drawing/equivalence와 실제 common/ON/NC continuity pending |
| Reset | NW3-A06-B3 geometry와 RST-GND 연결 통과 | actuator/service/reflow 실물 확인 pending |
| nice!nano socket | 2.54 mm pitch, 15.24 mm row spacing 통과 | exact receptacle/tail height/fully seated stack pending |
| M1.4 fastener | P3 좌 8/우 9 위치와 NPTH 통과 | exact screw/driver MPN, torque, ten cycles, keycap skirt, 2 N deflection pending |

## HIGH — 수정 후 검증기 0 종료 필요

### 1. 펌웨어 메타데이터가 실제 전원 회로와 모순된다

현재 실제 PCB 양쪽 전원 경로:

- `J_BAT1.1 BAT+ → SW_PWR1.1 BAT+`
- `SW_PWR1.2 NN_B+ → U1.RAW`
- `J_BAT1.2 GND → U1.GND_C`
- `SW_PWR1.3`은 NC, 무넷·무배선

그러나 다음 파일은 historical X3 계약인 `carrier_battery_nets=false`와 direct
nice!nano B+/B- 납땜을 주장한다.

- `firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_variant.json`
- `firmware/kc2_zmk/boards/shields/kc2_x3_v2/README.md`
- `tools/verify_kc2_x3_v2_zmk_firmware.py`

검증기까지 stale 값을 정답으로 기대하므로 현재 ZMK PASS에는 blind spot이
있다. JSON, README, verifier expectation, build-evidence metadata hash를 함께
갱신해야 한다. GPIO/keymap 배선 자체는 맞다.

### 2. Fabrication hard gate가 실패한다

`python -B -m tools.verify_kc2_x3_v2_fabrication` 종료 코드 `1`.

- 좌/우 inventory BOM CSV byte mismatch
- 좌/우 JLCPCB reference PCBA BOM/CPL byte mismatch

독립 비교 결과 의미 내용은 동일하고, tracked CSV는 CRLF인데 현재 generator가
LF를 생성하는 newline canonicalization 문제다. 총 6개 CSV를 LF 정책으로
재생성하거나 verifier의 canonical comparison 정책을 명확히 한 뒤 hard gate가
0으로 끝나야 한다.

PCBA BOM/CPL은 hand-assembly/reference only이며
`bom_cpl_upload_authorization=false`이다. JLCPCB에 업로드하면 안 된다.

### 3. Render evidence가 source-bound deterministic gate를 통과하지 못한다

`tools.verify_kc2_x3_v2_render` 실패:

- `kc2_joined_top.png` regenerated raw SHA mismatch
- `kc2_join_seam_zoom.png` regenerated raw SHA mismatch

다음 좌우 개별 PNG는 2026-08-20 historical 32/45-key/H-REG 산출물이며 현재
70-key/P3 증거가 아니다.

- `renders/left_top.png`, `left_bottom.png`
- `renders/right_top.png`, `right_bottom.png`

`renders/coupon_top.png`, `coupon_bottom.png`는 위 32/45-key/H-REG 좌우
렌더와 별개의 stale 3-key coupon 렌더이며, 현재 coupon 이전 형상이므로 현재
coupon 증거가 아니다.

현재 Windows 사진 앱에 띄운 `kc2_joined_top.png`의 배열 자체는
31+39=70키 V5 형상과 일치하지만, 주문 증거로 사용하려면 renderer와 manifest를
다시 생성·검증해야 한다. historical PNG는 제거 또는 명시적 archive 처리한다.

### 4. Footprint/generator provenance가 충분히 hash-bound되지 않았다

활성 footprint 파일은 `third_party/kc2.pretty`에 존재하고 embedded fallback은
사용하지 않는다. 다만 fabrication/generation manifest가 실제 사용된
`.kicad_mod`와 generator source SHA를 충분히 묶지 않는다. consumed footprint
path+SHA와 generator SHA를 manifest에 추가해야 재생성 추적성이 완결된다.

## MEDIUM — 공차 여유와 검증 범위

- 일반 copper-to-Edge.Cuts 최소:
  - Left `0.5000 mm`
  - Right `0.5079 mm`
  - 프로젝트 기준 `0.50 mm`는 통과하지만 여유가 거의 없다.
- 결합 PCB 최소 외곽 간격: `1.10 mm`, 요구 `1.00 mm` 대비 여유 `0.10 mm`.
- M1.4 디지털 최소 여유:
  - head↔component: left `1.3375`, right `1.2250 mm`, 요구 `1.20`
  - head↔copper/via: left `0.8750`, right `0.9607 mm`, 요구 `0.85`
  - head↔PCB edge: left `2.1500`, right `2.2125 mm`, 요구 `2.10`
  - head↔housing edge: left `2.0500`, right `2.1125 mm`, 요구 `2.00`
- Choc socket fillet↔housing 평면 여유 최소 `0.3357 mm`, 요구 `0.30 mm`.
- 이번 세션에는 Python 3.12/CadQuery 2.8 환경이 없어 STEP/STL housing
  verifier를 직접 재실행하지 못했다. 이는 이번 감사 세션만의 coverage
  limit이다. 기존 hash-bound housing report는 읽었지만, support-route 결함을
  잡는 검증 자체를 먼저 보강해야 한다.
- PCB-only 프로젝트라 schematic/ERP parity가 없다. DRC가 깨끗하다는 사실만으로
  net intent를 증명할 수 없으며 별도 connectivity verifier가 필수다.
- 통합 PCB unittest는 이번 감사 세션에서 KiCad SWIG 객체 lifetime 오류로 한
  프로세스 반복 실행이 실패했다. 이 역시 session-only coverage limit이며,
  개별 release verifier는 새 프로세스에서 동작했다.
- coupon reproducibility test 1개는 CRLF/LF byte 차이로 실패했다.

### 재현 명령

저장소 루트에서 각 KiCad 검증기를 새 프로세스로 실행한다.

```powershell
$kpy = 'C:\Program Files\KiCad\10.0\bin\python.exe'
& $kpy -B -m tools.verify_kc2_x3_v2
& $kpy -B tools\verify_kc2_connectivity.py `
  hardware\kicad\kc2_left\kc2_left.kicad_pcb `
  hardware\kicad\kc2_right\kc2_right.kicad_pcb
& $kpy -B -m tools.verify_kc2_x3_v2_fabrication
& $kpy -B -m tools.verify_kc2_x3_v2_render
& $kpy -B -m tools.verify_kc2_x3_v2_zmk_firmware
```

Housing 검증은 CadQuery 2.8이 설치된 별도 Python 3.12 환경에서 실행한다.

```powershell
python -B -m tools.verify_kc2_x3_v2_housing
```

## 디지털 통과 사항

| 항목 | 결과 |
|---|---|
| KiCad DRC | 좌우 각각 violations 0, unconnected 0, schematic parity 0 |
| 배열 | left 31 + right 39 = 70, 최대 1.75U |
| Stabilizer | `STAB*` 0개 |
| Switch 위치 | 최대 오차 `0.0001 mm` |
| joined keycap gap | 상위 4행 `1.8000 mm`, 하단 `1.7999 mm` |
| joined PCB gap | row-center `3.80 mm`, 전체 최소 `1.10 mm` |
| nice!nano | left USB_OUT_LEFT, right USB_OUT_RIGHT, antenna inward |
| matrix | duplicate contact nets, row/column islands, col2row diode direction 통과 |
| diode | 좌 31/우 39, exact 1N4148W-13-F, B.Cu, pad1=row/cathode |
| power/reset | BAT+/NN_B+/GND/RST 실제 copper island 통과 |
| M1.4 NPTH | left 8/right 9, P3 좌표, `1.60 mm`, unnetted/copper-free |
| routing | left 616 items, right 803 items, DSN/SES/hash 일치 |
| mechanical | hash-bound A4 1:1 PDF/SVG 통과 |
| Gerber/Excellon | flat 15-entry 좌/우 ZIP, 필수 layer와 PTH/NPTH 분리, geometry/hash 통과 |
| ZMK | 70-key GPIO/transform/source provenance 통과. 로컬 fresh UF2는 없음 |

DRC 결과에는 다음 한계가 있다.

- 프로젝트는 `missing_courtyard`, `track_not_centered_on_via`,
  `tuning_profile_track_geometries`, `footprint_filters_mismatch`,
  `footprint_type_mismatch` 검사를 전역 ignore한다.
- `U1`, `BAT1`과 일부 mechanical footprint에는 courtyard가 없으므로, clean
  DRC만으로 실제 component body overlap을 증명할 수 없다. 이 범위는 전용
  geometry/housing verifier와 실물 first article로 별도 검증해야 한다.

JLCPCB 공식 capability의 현재 공개 기준은 1 oz, 1- 및 2-layer 일반
track/spacing `0.10/0.10 mm`이다. `0.15/0.15 mm`는 solder mask로 덮인 trace
coil에 적용되는 별도 기준이다. routed edge-to-copper와 NPTH-to-track 최소치는
각각 `0.2 mm`다. 현재 PCB는 이 제조 최소치보다 엄격한 프로젝트 규칙으로
DRC를 통과했다. 그러나 JLCPCB
DFM은 하우징 지지대와 솔더마스크 마모, 구매 나사/배터리 stack을 검증하지
않으므로 본 보고서의 mechanical gate가 우선한다.

공식 기준: <https://jlcpcb.com/capabilities/pcb-capabilities>

## 새 Gerber를 만들기 전 조치 순서

1. `CON-ARCH-006`에 따라 17개 support의 22개 track segment hit를 제거한다.
2. 일반 key-load support에 B.Cu/B.Mask wear-surface clearance 검사를 추가한다.
3. Python 3.12 + CadQuery 2.8 환경에서 housing verifier와 housing tests를 다시
   실행한다.
4. stale firmware battery metadata와 verifier expectation을 고친다.
5. CSV newline 정책을 고정하고 BOM/CPL/fabrication manifest를 재생성한다.
6. joined/side/coupon render와 render manifest를 현재 source에서 재생성한다.
7. consumed footprint와 generator SHA binding을 추가한다.
8. exact 구매 부품 MPN과 controlled drawing을 확정한다.
9. coupon/first article을 제작하고 4개 physical evidence bundle을 채운다.
10. 모든 수정 후에만 좌우 PCB route/DRC/Gerber/Excellon/JLCPCB ZIP을 새로
    생성한다.

## 새 Gerber 생성 후 최종 품질 게이트

다음이 모두 만족되어야 주문할 수 있다.

- 좌우 fresh KiCad DRC: error=0, warning=0, unconnected=0
- connectivity verifier: 좌우 PASS
- fabrication, mechanical, housing, outline, render, firmware verifier: 모두 exit 0
- `tools.verify_kc2_x3_v2`: exit 0 및 `ORDER READY`
- physical evidence 4 bundle: source-bound artifact와 측정값 포함, 모두 PASS
- support/routed-copper 교차: 0
- exact fastener/driver/battery/switch/socket/power-switch traceability 완료
- 새 source/route/output SHA manifest 일치
- left/right JLCPCB ZIP을 각각 별도 주문으로 업로드
- PCBA reference BOM/CPL은 업로드하지 않음
- JLCDFM/견적 미리보기에서 outline, drill, board size를 마지막으로 육안 확인

## 결론

현재 보고서 맨 위에 기록된 SHA-256과 정확히 일치하는 좌·우 bare-PCB ZIP과
시험 coupon ZIP은 JLCPCB에 각각 업로드하여 제한 시제품을 제작해도 된다.
이 제작물은 남은 실물 coupon·체결·하우징·전원·RF 증거를 수집하기 위한
first article이다.

다만 `order_ready=false`이므로 양산 수량 주문, PCBA 주문, 일반 부품 조달,
reference BOM/CPL 업로드는 아직 승인하지 않는다. 시제품 실측이 끝난 뒤
물리 evidence bundle을 채우고 양산 판정을 별도로 갱신한다.
