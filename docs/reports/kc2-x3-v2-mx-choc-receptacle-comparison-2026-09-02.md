# KC2 X3 V2 MX·Choc V2 개별 Receptacle 비교 보고서

> 작성일: 2026-09-02  
> 활성 대상: `kc2-x3-v2`  
> 관련 요구사항: `CON-ARCH-004`, `CON-ARCH-006`  
> 사용자 수리 시나리오: 고장 switch 교체 약 10회

## 결론

개별 top/top-flush receptacle을 MX와 Choc V2 양쪽에 사용하는 것은 원리상
가능하다. 그러나 현재 권장 구조는 다음과 같다.

| Switch mode | 권장 구조 | 판정 |
|---|---|---|
| MX 5-pin | 전기 핀별 저프로파일 receptacle 2개 또는 direct solder | 조건부 권장 |
| Choc V2 | 기존 전용 bottom-side Choc socket | 기본안 유지 |
| Choc V2 + 개별 receptacle | 별도 coupon/variant에서 검증 | 실험 후보 |
| MX와 Choc에 동일 receptacle SKU 사용 | exact pin drawing과 coupon 전까지 금지 | 미확정 |

즉, **MX는 개별 receptacle로 확장할 가치가 크지만, Choc V2 socket까지 같은
방식으로 바로 통일하는 것은 추천하지 않는다.**

## 현재 footprint의 차이

### MX 전기 접점

현재 `SW_Choc_V2_Socket_MX_THT` footprint에는 이미 두 개의 plated MX
contact가 있다.

| Pad | 위치 mm | Copper pad | Drill |
|---|---:|---:|---:|
| 1 | `(2.54, -5.08)` | `2.50 mm` | `1.50 mm` PTH |
| 2 | `(-3.81, -2.54)` | `2.50 mm` | `1.50 mm` PTH |

따라서 exact receptacle MPN의 finished-hole 조건만 맞추면 direct solder와
개별 receptacle을 같은 electrical pad에서 선택할 수 있다.

### Choc V2 전기 접점

현재 Choc V2는 switch pin 영역을 copper-free NPTH/clearance로 두고, 별도의
bottom-side `CPG135001S30` class SMD socket pad로 matrix net을 받는다.

대표 switch-pin opening은 약 `3.0 mm` copper-free NPTH이며, 개별 receptacle이
요구하는 약 `1.5 mm`급 plated hole과 구조가 다르다. Choc V2 개별 receptacle을
사용하려면 다음을 새로 설계해야 한다.

- Choc pin 위치의 plated PTH
- copper pad와 annular ring
- top flange와 switch bottom 간격
- receptacle barrel/tail의 하부 돌출
- 각 Choc contact와 기존 matrix net 연결
- 기존 bottom Choc SMD socket pad의 유지 또는 제거 정책

이는 단순 BOM 변경이 아니라 footprint, routing, housing을 다시 여는 변경이다.

## 전용 Choc bottom socket의 장단점

### 장점

- Choc 계열 flat terminal을 위해 설계된 contact와 insertion depth를 사용한다.
- socket body가 PCB 아래에 있어 Choc V2 switch의 낮은 상면 안착 높이를
  변경하지 않는다.
- 한 부품의 nylon body가 두 contact의 정렬·회전·변형을 함께 제어한다.
- 현재 PCB footprint, bottom courtyard, BOM/CPL, housing cutout이 이 구조를
  기준으로 이미 설계되어 있다.
- 공식 `CPG135001S30` specification의 100 mating cycles는 사용자가 원하는
  약 10회 고장 교체 시나리오보다 충분히 크다.

### 단점

- 약 `9.55 x 6.85 x 1.8 mm`급 body가 PCB 하부 공간을 사용한다.
- 하부 housing에 socket body·pad·fillet용 open cutout이 필요하다.
- diode, support 및 housing plate와의 충돌 검사가 복잡하다.
- SMD socket 납땜과 방향 확인이 필요하다.
- Kailh 공식 판매 설명은 `CPG135001S30`을 Choc V1용으로 표현하므로, active
  Choc V2 exact switch MPN과의 실제 호환성은 현재 SRS가 요구하는 physical
  coupon으로 닫아야 한다.

공식 자료:

- Kailh `CPG135001S30` specification:
  <https://www.kailhswitch.com/Content/upload/pdf/202115927/CPG135001S30-data-sheet.pdf>
- Kailh socket product page:
  <https://www.kailhswitch.com/mechanical-keyboard-switches/box-switches/choc-type-hot-swap-socket.html>

## Choc V2 개별 receptacle의 장단점

### 잠재적 장점

- 큰 하부 nylon socket body를 없앨 수 있다.
- exact top-flush part를 찾으면 housing bottom opening을 작게 만들 여지가 있다.
- direct-solder와 hot-swap을 같은 Choc pin PTH에서 선택하도록 설계할 수 있다.
- MX와 동일한 조달 계열을 쓸 수 있다면 BOM 종류가 줄어들 수 있다.
- 고장 교체가 약 10회뿐이므로 매우 높은 cycle rating은 중요하지 않다.

### 결정적 위험

- Choc V2 terminal은 MX terminal과 위치가 다르다. 폭·두께의 동등성은 exact
  active Choc V2 MPN drawing과 physical coupon 검증 전까지 확인되지 않았다.
- generic 0305/7305 contact의 원형/정사각 핀 수용 범위만으로 Choc flat
  terminal 호환을 가정할 수 없다.
- 동일 receptacle SKU가 MX의 서로 다른 두 blade와 Choc의 두 terminal을 모두
  적절한 force로 잡는다는 근거가 없다.
- 7305의 약 `0.36 mm`급 top flange나 0305의 더 큰 상면 돌출도 low-profile
  Choc switch의 완전 안착과 높이를 바꿀 수 있다.
- 개별 두 부품은 전용 nylon body처럼 contact 정렬과 회전을 함께 잡아주지
  않는다.
- 무보강판에서 switch retention과 흔들림이 더 불리할 수 있다.
- receptacle barrel은 PCB 아래로 돌출하므로 하부 공간이 반드시 더 좋아진다고
  단정할 수 없다.
- 현재 `3.0 mm` NPTH를 `1.5 mm`급 plated hole로 바꾸면 copper, diode,
  MX geometry와 routing을 모두 다시 검증해야 한다.

## Mill-Max 계열 치수 관점

| 계열 | 공식 mounting-hole 조건 | Top flange | Choc 판단 |
|---|---|---|---|
| 0305 | `1.50/1.55 mm` solder-mount hole | 약 `0.64 mm`급 | 상면 높이 위험, coupon 필수 |
| 7305 | `1.52 mm minimum` solder-mount hole | 약 `0.36 mm`급 | 더 낮지만 current hole과 drop-in 불가 |
| zero-profile press-fit | exact MPN별 정밀 PTH | surface flush 가능 | 가장 매력적이나 tooling/공차와 flat-pin contact 미확정 |

Mill-Max #47 contact 계열은 대략 `0.64-0.94 mm` 원형 핀 또는 `0.64 mm`
square pin 범위를 제시한다. 이 범위는 Choc V2 flat terminal의 폭과 두께를
직접 보증하지 않는다.

공식 자료:

- Mill-Max receptacle catalog:
  <https://www.mill-max.com/sites/default/files/external/catalog/2019-10/153M-201M_0.pdf>
- Mill-Max zero-profile receptacle 안내:
  <https://www.mill-max.com/products/new/zero-profile-press-fit-receptacles>

## 선택 가능한 PCB 아키텍처

### 안 1 — 현재 혼합 구조 유지

- Choc V2: bottom SMD socket
- MX: direct solder 또는 새 개별 receptacle

장점은 Choc의 검증된 전용 contact 구조를 유지하면서 MX만 사용자 선택형으로
확장할 수 있다는 점이다. 현재 가장 추천한다.

### 안 2 — 양쪽 모두 개별 receptacle

- Choc V2 pin용 receptacle 2개
- MX pin용 receptacle 2개
- 두 family의 위치가 다르므로 키당 최대 네 receptacle 위치가 필요

장점은 assembly 철학을 통일할 수 있다는 점이다. 단점은 hybrid footprint의
copper와 hole 밀도가 높아지고, 동일 SKU 공유 여부가 불확실하며, low-profile
Choc seating risk가 커진다는 점이다.

### 안 3 — Choc receptacle 전용 별도 PCB variant

현재 V2와 분리하여 exact Choc switch/receptacle coupon을 먼저 검증한다. 성공한
경우에만 main hybrid footprint로 역통합한다. 실험 비용과 production risk를
분리할 수 있어 안 2를 검토한다면 이 순서가 안전하다.

## 필수 coupon 검증

정확한 Choc V2 switch MPN과 receptacle MPN을 고정한 뒤 다음을 확인한다.

1. Choc terminal 폭·두께와 contact acceptance
2. insertion force와 extraction force
3. PCB 상면 완전 안착 및 key height 변화
4. center/locator feature의 유효 삽입 깊이
5. switch wobble, rotation 및 pull-out
6. plated finished-hole 분포와 receptacle 삽입/납땜·press-fit force
7. bottom barrel/tail과 diode/socket/housing/support 간섭
8. 접촉저항과 matrix press/release
9. 사용자가 정한 10회 고장 교체 시나리오 후 contact·pad·socket 상태
10. Choc/MX/direct-solder mode의 상호 배타적 조립과 오조립 방지

## SRS 영향

현재 `CON-ARCH-004` AC-2는 Choc V2 switch pin 영역에 copper pad와 plated
switch-pin hole을 금지한다. 개별 receptacle을 채택하려면 implementation 전에
다음부터 변경해야 한다.

- Choc V2 socket-only 계약
- Choc switch-pin copper/PTH 금지
- mutually-exclusive assembly mode 목록
- footprint geometry와 BOM/assembly silkscreen
- coupon AC와 housing/support clearance gate
- fabrication drill 및 source/hash manifest

## 최종 권고

1. **MX:** 개별 low-profile/top-flush receptacle을 조건부 지원한다.
2. **Choc V2:** 현재 전용 bottom socket을 기본안으로 유지한다.
3. **Choc 개별 receptacle:** 별도 coupon/variant로만 연구한다.
4. **동일 receptacle SKU 공유:** exact MX/Choc terminal drawing과 실물 coupon이
   모두 통과할 때만 채택한다.

Choc V2까지 개별 receptacle로 바꾸는 아이디어는 가치가 있지만, 현재는 하부
공간 절감 가능성보다 **flat terminal compatibility와 low-profile 완전 안착
위험이 더 크다.** 따라서 main PCB에는 먼저 MX receptacle 선택지만 추가하고,
Choc은 전용 socket을 유지하는 단계적 접근이 가장 안전하다.
