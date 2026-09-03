# KC2 X3 V2 MX 소켓 선택 조립 가능성 보고서

> 작성일: 2026-09-02  
> 활성 대상: `kc2-x3-v2`  
> 관련 요구사항: `CON-ARCH-004`, `CON-ARCH-006`  
> 검토 범위: MX direct solder와 사용자 선택형 MX hot-swap의 공존 가능성

## 결론

# CONDITIONALLY FEASIBLE — 가능하지만 현재 설계에는 바로 적용할 수 없다

사용자가 각 키 위치에서 다음 중 하나를 선택하는 구조는 구현 가능하다.

1. MX 5-pin switch 직접 납땜
2. MX 전기 핀용 개별 receptacle 2개를 설치한 hot-swap
3. 기존 Choc V2 bottom-side socket 조립

단, 세 assembly mode는 **서로 배타적**이어야 한다. 같은 키 위치에 Choc
socket과 MX receptacle을 함께 실장하면 안 된다.

권장 결론:

- **상면 Kailh/Gateron형 일체형 MX SMD socket:** 기각
- **상면 또는 top-flush 개별 Mill-Max형 receptacle 2개:** 조건부 권장
- **현재 PCB에 그대로 끼우는 drop-in 주장:** 금지

## 현재 설계와 SRS 상태

`CON-ARCH-004`는 현재 다음과 같이 제한한다.

- Choc V2: bottom-side hot-swap socket only
- MX: top-side direct solder only
- MX hot-swap: unsupported

따라서 PCB나 footprint를 변경하기 전에 `CON-ARCH-004`의 requirement,
AC-1, AC-3, AC-7, AC-8, AC-9 및 assembly documentation을 먼저 변경해야 한다.

현재 KC2-owned footprint `SW_Choc_V2_Socket_MX_THT`의 MX 전기 접점은 키당
두 개다.

| Pad | 위치 mm | Copper pad | Drill | 현재 용도 |
|---|---:|---:|---:|---|
| 1 | `(2.54, -5.08)` | `2.50 mm` | `1.50 mm` PTH | MX direct solder |
| 2 | `(-3.81, -2.54)` | `2.50 mm` | `1.50 mm` PTH | MX direct solder |

같은 footprint에는 별도의 bottom-side Choc V2 SMD contact가 있고, 각 alternate
contact는 동일한 intended matrix net에 묶여 있다. 따라서 개별 receptacle을
두 MX PTH에 설치하는 방식은 matrix 논리를 바꿀 필요가 없다.

## 선택지 비교

### A. Kailh CPG151101S11-16 계열 일체형 MX SMD socket을 상면 장착

**권장하지 않는다.**

Kailh 공식 도면의 socket body는 약 `14.50 x 5.89 mm`, 높이 약 `1.85 mm`이고,
전용 대형 switch-pin opening과 SMD land가 필요한 별도 PCB layout을 사용한다.
현재 `1.50 mm` MX PTH 두 개에 끼우는 부품이 아니다.

이 socket은 switch pin이 PCB를 통과해 socket에 들어가는 일반 하부 실장
구조에 맞춰 사용한다. 상면에 배치하면 socket body가 MX switch 하우징과 PCB
안착면 사이를 차지하여 다음 문제가 발생한다.

- switch가 PCB에 완전히 안착하지 않음
- center post와 두 locator pin의 유효 삽입 깊이 감소
- 무보강판에서 switch 높이·기울기·흔들림 증가
- 현재 Choc/MX hybrid hole 및 diode geometry와 추가 충돌 가능
- 모든 70개 위치에 전용 F.Cu SMD land와 대형 opening 추가 필요

따라서 단순히 기존 footprint에 Kailh MX socket pad를 상면 복사하는 방식은
채택하지 않는다.

공식 자료:

- Kailh `CPG151101S11-16`, KH-PS2206-43 Rev. A:
  <https://m.kailhswitch.com/Content/upload/pdf/202215927/CPG151101S11-16.pdf>
- Kailh MX socket 제품 정보:
  <https://www.kailhswitch.com/news/kailh-mx-type-hot-swap-socket-50738670.html>

### B. MX 전기 핀별 개별 receptacle 2개

**조건부로 가능하며 권장 후보다.**

사용자가 MX PTH 두 곳에 receptacle을 설치하면 switch pin이 receptacle contact에
들어가고, receptacle을 설치하지 않은 사용자는 기존처럼 switch pin을 직접
납땜할 수 있다. 추가 MX SMD land 없이 동일 matrix pad를 공유할 수 있다는
장점이 있다.

후보군:

| 후보 | 공식 mounting-hole 조건 | 현재 1.50 mm drill과 관계 | 판단 |
|---|---|---|---|
| Mill-Max 0305 계열 | `1.50/1.55 mm` solder-mount hole | nominal 치수는 가깝지만 finished-hole 공차 검증 필요 | 쿠폰 후보 |
| Mill-Max 7305 계열 | `1.52 mm minimum` solder-mount hole | 현재 nominal 1.50 mm는 그대로 승인할 수 없음 | footprint 재설계 후보 |
| keyboard-rated top-flush/zero-profile 계열 | exact MPN별 상이 | 현재 hole과 pin acceptance를 새로 계산해야 함 | 장기 우선 후보 |

Mill-Max 공식 catalog는 0305를 `1.50/1.55 mm` mounting hole, 7305를
`1.52 mm minimum` mounting hole로 제시한다. 다만 generic receptacle contact의
원형/정사각 핀 수용 범위만으로 폭이 다른 MX flat blade 두 개와의 적합성을
가정하면 안 된다. **정확한 keyboard-rated MPN과 contact drawing을 먼저
고정해야 한다.**

공식 자료:

- Mill-Max pin receptacle catalog:
  <https://www.mill-max.com/sites/default/files/external/catalog/2019-10/153M-201M_0.pdf>
- Mill-Max hot-swap mechanical keyboard 사례:
  <https://www.mill-max.com/sites/default/files/external/assets/2024-11/mmax-pins-recepticles-brochure-web_version-final.pdf>

## “상면 장착”에 대한 정확한 의미

개별 receptacle 방식에서도 다음을 구분해야 한다.

- **상면 돌출 flange:** switch bottom이 flange 위에 걸려 완전 안착하지 않을 수
  있다.
- **top-flush/zero-profile:** PCB 상면과 거의 같은 높이로 마감되어 switch
  안착에는 유리하지만, plated-hole 공차와 press-fit tooling 요구가 더 엄격하다.
- **하부 flange:** switch는 PCB에 안착하기 쉽지만 하우징 내부 돌출이 커질 수
  있으며 사용자가 요구한 상면 장착과 다르다.

따라서 이번 요구에는 top-flush 또는 상면 돌출이 매우 작은 exact receptacle을
우선 검토한다. 단순히 “Mill-Max”라는 상표나 0305/7305 family 이름만으로
승인하지 않는다.

## 무보강판 구조의 추가 위험

소켓은 전기 접촉을 제공하지만 switch를 기계적으로 고정하는 plate가 아니다.
KC2는 무보강판이므로 hot-swap MX mode에서는 다음 조건이 중요하다.

- 5-pin PCB-mount MX switch만 정식 지원
- center post와 두 locator pin이 PCB에 충분히 삽입되어야 함
- switch bottom이 PCB 상면에 완전히 안착해야 함
- 3-pin plate-mount MX는 별도 plate/retainer 없이는 정식 지원하지 않음
- keycap 제거 및 반복 switch 탈착 시 PCB pad와 receptacle이 들리지 않아야 함
- switch 흔들림, 회전, pull-out 및 keycap skirt 높이를 실측해야 함

## PCB와 하우징에 필요한 변경

정확한 receptacle MPN이 정해진 뒤 다음을 재설계한다.

1. finished PTH diameter와 fabrication tolerance
2. copper pad diameter와 annular ring
3. top flange diameter/height와 MX switch bottom 간섭
4. barrel/tail의 PCB 하부 돌출
5. bottom Choc socket, diode body/pad/fillet 및 MX locator hole과의 간격
6. 하부 housing cutout과 31/39 key-load support 위치
7. receptacle용 F.Fab/F.CrtYd/B.Fab/B.CrtYd 및 assembly marking
8. BOM과 silkscreen의 mutually-exclusive assembly 안내

현재 하부 지지대와 B.Cu route 간 wear-surface 문제도 별도로 열려 있다.
MX receptacle 변경은 이 기존 문제를 우회하지 못하며 housing/support/route를
함께 다시 검증해야 한다.

## 필수 coupon 시험

전체 PCB에 적용하기 전에 최소 3-key 이상의 전용 coupon으로 다음을 확인한다.

1. JLCPCB 제작 후 실제 plated finished-hole 직경 분포
2. receptacle 삽입·납땜 또는 press-fit force와 pad 손상
3. 두 종류 MX flat electrical pin의 삽입력·접촉저항·유지력
4. 5-pin MX switch의 center/locator 완전 안착
5. 상면 flange 때문에 발생하는 switch 높이·기울기·흔들림
6. receptacle bottom barrel/tail과 Choc socket/diode/housing 간섭
7. 고장 난 switch 교체 용도를 반영한 KC2 제안 acceptance gate인 10회 switch
   교체 사이클 후 접촉저항, pad peel, socket spin/pull-out 확인(`10회`는
   사용자가 정한 수리 시나리오이며 Mill-Max 공식 정격이나 기존 SRS
   threshold가 아님)
8. direct-solder mode가 동일 PTH에서 정상 조립되는지
9. Choc bottom socket mode와 MX receptacle mode의 상호 배타적 조립
10. keycap 장착 상태에서 타건 변위와 pull-out

CAD-only 확인이나 nominal hole 치수만으로는 주문 승인을 내리지 않는다.

## 권장 구현 방향

1. `CON-ARCH-004`를 먼저 변경하여 세 가지 상호 배타적 assembly mode를 정의한다.
2. exact keyboard-rated low-profile receptacle MPN을 선정한다.
3. current `1.50 mm` PTH를 유지할지, 7305/top-flush 규격에 맞춰 바꿀지
   finished-hole 기준으로 결정한다.
4. 작은 coupon을 제작하여 상면 안착과 반복 탈착을 검증한다.
5. coupon 통과 후 70-key footprint, housing, route, DRC, fabrication 및 physical
   evidence를 전부 재생성한다.

## 최종 답변

사용자가 MX direct solder와 MX hot-swap 중 하나를 선택하는 설계는 **가능하다.**
그러나 **Kailh MX 일체형 SMD socket을 PCB 상면에 다는 방식은 채택하지 않는
것이 맞다.**

가장 현실적인 방향은 **키당 개별 top-flush/저프로파일 receptacle 2개와 기존
direct-solder PTH를 공용화하는 것**이다. 다만 현재 PCB는 drop-in 호환 상태가
아니며, exact MPN 선정, SRS 변경, finished-hole 재설계 및 실물 coupon 검증을
거친 뒤에만 적용할 수 있다.
