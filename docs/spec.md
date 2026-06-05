# KC2 Keyboard Specification

## 개요

KC2는 KC1 핸드와이어링 키보드의 배열 철학과 결합/분리 사용성을 계승한 2세대 PCB 설계다. 한국어 2벌식 입력 습관을 반영한 오른손 `B` 키를 유지하며, 보강판 없이 PCB에 스위치를 직접 납땜한다. 상부 하우징은 두지 않지만, 3D 프린터로 만든 하부 바닥판에 PCB를 고정하고 그 아래에 실리콘 feet를 부착한다.

## 핵심 요구사항

- 이름: KC2
- 형식: 좌우 분리형 split keyboard
- 배열: 일반 row-stagger 기반
- 키 수: 71키
- 펌웨어: ZMK
- 컨트롤러: nice!nano v2, 좌우 각 1개
- 연결: BLE 중심, USB는 firmware flash/debug 및 필요 시 유선 출력용
- 백라이트/RGB: 없음
- 컨트롤러 소켓: 디바이스마트 상품번호 5494 `싱글라운드소켓(64핀)`, 2.54 mm pitch, 1열, round socket을 절단해 사용
- 배터리: 디바이스마트 상품번호 1376800 `TW301525`, 3.7 V, 80 mAh, Li-Po, A1251-02 출력단자, 15 mm x 25 mm급
- 배터리/컨트롤러 전원 연결: X3 compact controller tab에서는 A2506 PCB 커넥터와 carrier-PCB 전원 solder pad를 모두 사용하지 않고, 배터리 lead를 nice!nano v2 `B+`/`B-` pad에 직접 납땜한다.
- PCB 전원 커넥터/패드: 사용하지 않는다. X3 carrier PCB에는 `BAT+`, `BAT-`, `NN_B+`, `NN_B-` pad, trace, exposed copper를 두지 않는다.
- 키스위치: 특정 모델을 문서에 고정하지 않는다.
- 스위치 실장: PCB 직접 납땜
- 스위치 footprint 기준: 특정 키스위치 전용 footprint를 피하고, 가능한 한 여러 키스위치를 꽂을 수 있는 다중 호환 switch hole/pad pattern을 만든다.
- 큰 키: 무보강판에서 실제로 체결 가능한 PCB-mounted/PCB-retained stabilizer hole/cutout를 설계한다. 검증 전 generic/MX-style placeholder hole로 발주하지 않는다.
- 프로그래밍용 택트 스위치: 디바이스마트 상품번호 1322056 `NW3-A06-B3`, SMD micro tact switch, 6.1 mm x 3.7 mm급 body, 2.55 mm급 높이
- 전원 스위치: 없음. 일반 사용 중 hard power-off는 제공하지 않는다. 장기 보관/정비 시에는 nice!nano v2 `B+` 또는 `B-`에 직접 납땜된 배터리 lead를 desolder하거나 외부 lead 분리 구조로 차단한다.
- 보강판: 없음
- 하우징: 상부 하우징 없음. 3D 프린터 하부 바닥판을 사용한다.
- PCB 수량: 좌우 독립 PCB 2장

## 제조 파일 제출

KC2 main PCB는 검증된 X3 no-stabilizer 버전이며, 좌우 독립 PCB 2장이므로 PCB 제조사 제출 파일도 좌/우를 분리해서 다룬다. `hardware/kicad/fabrication/kc2_fabrication.zip`처럼 좌/우 산출물을 함께 담은 합본 ZIP은 저장소 내부 검증/보관용 묶음이며, JLCPCB 같은 제조사에 단일 비패널 PCB 주문으로 그대로 제출하지 않는다.

기본 주문 방식은 좌/우 fabrication directory를 각각 별도 ZIP으로 묶어 별도 PCB 주문으로 제출하는 것이다.

- Left: `hardware/kicad/fabrication/kc2_left/`
- Right: `hardware/kicad/fabrication/kc2_right/`

JLCPCB 제출용 개별 ZIP은 다음 두 파일을 사용한다.

- Left order ZIP: `hardware/kicad/fabrication/kc2_left_jlcpcb.zip`
- Right order ZIP: `hardware/kicad/fabrication/kc2_right_jlcpcb.zip`

각 ZIP에는 Gerber copper, solder mask, solder paste, silkscreen, Edge.Cuts, Gerber job 파일뿐 아니라 PTH/NPTH Excellon drill 파일과 drill map/report를 함께 포함해야 한다. "거버 파일"이라고 부르더라도 drill 파일을 빼면 발주용 패키지로 인정하지 않는다.

좌우 PCB를 한 주문 안에 넣으려면 단순히 두 보드 파일 세트를 한 ZIP에 섞지 말고, 의도적인 customer panel Gerber를 별도로 생성한 뒤 서로 다른 디자인 2개를 포함한 panelized order로 제출한다. 이 경우 제조사의 different-design/panel 옵션, 추가 비용, V-cut/tab-route 분리 조건을 주문 전에 확인한다.

이전 soldered, hotswap, x1, x2 KiCad 산출물은 `hardware/kicad/draft/` 아래에 보관한다. 제조와 검증의 기본 진입점은 `hardware/kicad/kc2_left/`와 `hardware/kicad/kc2_right/`이다.

## 한국어 입력 요구사항

KC2는 KC1의 한글 2벌식 입력 방식을 이어받아 `ㅠ` 입력을 자연스럽게 하기 위한 오른손 `B` 키를 가진다.

KC1과의 관계는 배열 철학과 사용성의 계승이며, KC2의 하드웨어 프로젝트명과 펌웨어 식별자는 별도 세대인 `kc2`로 통일한다.

- QWERTY 기준 `B`는 왼손 알파열 위치에 유지한다.
- 오른쪽 하단에도 추가 `B` 키를 둔다.
- 오른쪽 하단 `B`는 한글 2벌식 `ㅠ`를 오른손으로 입력하기 위한 필수 키다.
- PCB 설계 시 오른쪽 하단 `B` 키를 삭제하거나 다른 키로 대체하지 않는다.

## 물리 구조

- 무보강판 구조다.
- 상부 하우징은 없다.
- PCB 아래에는 3D 프린터로 제작한 하부 바닥판을 둔다.
- PCB가 전기 회로이자 스위치 고정 구조물이다.
- 키스위치 모델은 고정하지 않고 PCB에 직접 납땜한다.
- 큰 키 stabilizer는 plate-mounted가 아니라, 무보강판에서 실제로 고정되는 PCB-mounted/PCB-retained 방식을 사용한다.
- PCB 외곽선은 키 배열, 결합부, controller 돌출부, USB-C 접근 방향을 따라 최대한 타이트하게 잡는다.
- 실리콘 feet는 PCB가 아니라 3D 프린터 하부 바닥판 아래에 부착한다.
- PCB와 하부 바닥판은 가능하면 M2 나사로 고정한다.
- M2 고정 홀을 둘 공간이 부족하면 접착제 고정을 대안으로 허용한다.
- 배터리, 납땜부, diode lead/pad, controller pin이 하부 바닥판 또는 책상과 직접 닿아 쇼트되지 않도록 한다.

## 무보강판 스테빌라이저

KC2는 상부 보강판이 없는 PCB 직접 납땜 구조이므로, 큰 키의 stabilizer는 단순한 plate-mounted low-profile stabilizer를 사용할 수 없다. 조사 결과 Kailh Choc V1/V2 계열 stabilizer는 일반적으로 PCB cutout과 1.2 mm급 switch plate cutout을 함께 요구한다. 따라서 KC2에서는 "PCB에 구멍만 있는 상태"로 실제 부품이 고정되는지 검증되지 않은 footprint를 발주용으로 인정하지 않는다.

5개 서브에이전트 검토 결론:

- stabilizer 적용 기준은 `2u 이상`으로 둔다.
- `1.75u` 이하 key는 기본적으로 stabilizer를 넣지 않는다.
- 현재 KiCad generator의 `KC2:PCB_Mount_2u_Stabilizer_NPTH`는 Cherry MX PCB-mount에서 온 형태에 가까운 provisional keepout/placement marker다. low-profile 무보강판 발주용 final footprint가 아니다.
- 최종 stabilizer family는 switch/keycap ecosystem과 함께 결정해야 한다. MX-style PCB stabilizer hole과 Choc/low-profile keycap/stabilizer를 섞어 발주하지 않는다.
- 실물 stabilizer, keycap underside, switch footprint, 하부 바닥판 간섭을 1:1 출력물 또는 test coupon으로 확인한 뒤 final drill/cutout를 고정한다.

스테빌라이저가 필요한 위치:

| Half | Key | Width | 위치 기준 | 결정 |
| --- | --- | --- | --- | --- |
| Left | `Shift` | 2.25u | Row 4, `Z` 왼쪽 | stabilizer 필수 |
| Left | `Space` | 2.25u | Row 5, 오른쪽 끝 | stabilizer 필수 |
| Right | `Backspace` | 2.25u | Row 1, `=` 오른쪽 | stabilizer 필수 |
| Right | `Enter` | 2.5u | Row 3, `"` 오른쪽 | stabilizer 필수 |
| Right | `Shift` | 2u | Row 4, `?` 오른쪽 | stabilizer 필수 |
| Right | `Space` | 2u | Row 5, `B_RH` 오른쪽 | stabilizer 필수 |

스테빌라이저를 넣지 않는 위치:

- Left `Tab` 1.5u
- Left `Caps Lock` 1.75u
- Right `\` 1.75u
- 모든 1.25u, 1u key

배치 규칙:

- 모든 stabilized key는 현재 KLE key width의 중심에 switch center를 두고, stabilizer pair를 key의 긴 축 방향으로 switch center 좌우에 대칭 배치한다.
- KC2의 wide key는 모두 수평 key이므로 stabilizer bar 방향은 좌우 방향이다.
- 2u, 2.25u, 2.5u key는 기본 후보로 2u stabilizer spacing을 검토하되, 실제 keycap underside의 보조 stem 간격과 stabilizer wire 규격을 실측해 확정한다.
- low-profile/Choc stabilizer를 유지하려면 무보강판에서도 고정되는 part이거나, 하부 바닥판/별도 3D printed retainer가 stabilizer 이탈을 막는 구조여야 한다. 단, 별도 retainer는 보강판을 새로 추가하는 결정이므로 발주 전에 별도 검토한다.
- 최종 footprint에는 stabilizer body courtyard, wire swing/insert keepout, PCB cutout, NPTH drill, copper keepout이 모두 포함되어야 한다.

제조 및 routing keepout:

- stabilizer NPTH/cutout에는 top/bottom copper, trace, via, pad, zone이 겹치면 안 된다.
- stabilizer hole edge에서 copper/trace/via까지 최소 0.50 mm, 목표 1.00 mm clearance를 둔다.
- stabilizer hole edge는 PCB outline에서 최소 4.0 mm, 가능하면 5.0 mm 이상 떨어뜨린다.
- diode pad, diode body, switch solder joint, M2 hole, 하부 바닥판 screw boss/rib는 stabilizer body courtyard와 겹치면 안 된다.
- routing과 diode 배치는 stabilizer footprint를 먼저 고정한 뒤 그 주변으로 피해서 잡는다. 공간이 부족하면 stabilizer hole을 줄이지 말고 diode 위치, diode package, trace layer, outline, M2 위치 순서로 재검토한다.
- 하부 바닥판은 stabilizer clip, wire, keycap 하강 공간을 막지 않아야 한다.

조사 근거:

- Keebio Choc stabilizer installation: https://docs.keeb.io/choc-stabs
- LowproKB Kailh Choc stabilizers: https://lowprokb.ca/products/kailh-choc-stabilizers
- Keebio Kailh Choc V2 stabilizers: https://keeb.io/products/kailh-choc-v2-stabilizers
- splitkb Cherry 2u PCB Mount Stabilizer: https://splitkb.com/products/cherry-2u-pcb-mount-stabilizer
- Keebio Kailh PG1350 2u footprint reference: https://raw.githubusercontent.com/keebio/Keebio-Parts.pretty/master/Kailh-PG1350-2u.kicad_mod

## 외형 및 결합 구조

- KC2는 KC1처럼 좌우 키보드를 붙였다 뗐다 할 수 있어야 한다.
- 좌우 half를 붙였을 때 맞닿는 안쪽 edge는 다른 외곽보다 얇게 만든다.
- 왼쪽 keyboard의 오른쪽 edge와 오른쪽 keyboard의 왼쪽 edge가 결합 edge다.
- 결합 edge는 키캡 간격과 손가락 간섭을 줄이기 위해 최소 여백을 목표로 한다.
- 바깥쪽 edge, 손바닥 접촉부, controller 돌출부는 강도와 라운딩을 우선한다.
- 일반 PCB 외곽 테두리는 keycap 외곽 기준 5.5 mm를 기본값으로 하며, 부품/배선 조건에 따라 5.0-6.0 mm 범위에서 조정한다.
- 좌우 half가 맞닿는 결합 edge는 keycap 외곽 기준 2.8 mm를 기본값으로 하며, 허용 범위는 2.5-3.0 mm로 둔다. 2.5 mm 미만은 반복 결합/분리 시 파손 위험 때문에 사용하지 않는다.
- X3를 결합 상태로 배치할 때는 오른쪽 `Y`/`H` 쪽 돌출부가 왼쪽 `T`/`G` 쪽 홈으로 들어가는 interlocked placement를 기본 reference로 둔다. 좌우 PCB Edge.Cuts 사이의 최소 joined placement clearance는 `1.0 mm`로 둔다.
- X3 오른쪽 `Y`/`H` 돌출부의 세로 inner Edge.Cuts 면은 X3 inner-edge routing relief가 적용된 `3.6 mm` margin을 유지한다. X방향 끼임 여유는 세로면을 후퇴시키지 않고 돌출부의 가로 ledge 시작점만 안쪽으로 `0.8 mm` relief 처리해 확보한다.
- 3D 프린터 하부 바닥판의 치수 팽창, 밀링 burr, 자석 정렬 오차를 흡수하기 위한 실사용 clearance 허용 범위는 `0.8-1.2 mm`이며, `0 mm` 접촉은 좌표 정렬 확인용으로만 사용한다.
- joined placement clearance는 하부 바닥판/자석/정렬 구조의 배치 기준이며, PCB inner-edge routing relief 또는 copper-to-edge clearance를 줄이기 위한 값이 아니다.
- 결합 edge의 얇은 영역에는 가능하면 pad, via, diode lead, wire strain relief, M2 홀을 두지 않는다.
- PCB edge-to-copper clearance는 일반 edge에서 1.0 mm 이상, 결합 edge에서 최소 0.8 mm 이상을 유지하되 가능하면 1.0 mm를 목표로 한다.
- PCB 외형은 단순 사각형이 아니라 키 배열 외곽을 따라 남는 공간을 최소화한다.
- controller가 놓이는 영역은 숫자열 바로 위에 붙은 돌출 탭 형태로 만든다.
- controller 돌출 탭의 X 위치는 결합 edge 쪽에 가깝게 두되, 탭의 결합면 쪽 끝은 실제 결합 edge보다 안쪽으로 들어가게 한다. 현재 draft 기준 왼쪽 half는 약 12 mm, 오른쪽 half는 약 17 mm recessed 배치로 둔다. 왼쪽 half는 오른쪽 결합 edge 쪽, 오른쪽 half는 왼쪽 결합 edge 쪽에 탭을 배치하되, 맞붙임을 방해하지 않아야 한다.
- controller 돌출 탭은 요철처럼 튀어나오되, 모서리는 둥글게 처리한다.
- controller 돌출 탭은 전기적 배치뿐 아니라 손가락/케이블/하부 바닥판 간섭을 함께 고려한다.
- M2 나사 홀은 키 스위치, stabilizer, diode, controller socket, battery, wire strain relief와 간섭하지 않는 중간 지점에 우선 배치한다.
- M2 나사 홀 배치가 불가능한 영역은 하부 바닥판과 접착 고정하는 후보 영역으로 둔다.
- M2 고정 홀은 NPTH 2.2 mm를 기본값으로 하고, screw head와 3D 프린터 boss를 위한 keepout은 지름 5.0 mm 이상으로 둔다.
- M2 홀 중심은 PCB 외곽에서 최소 4.0 mm, 가능하면 4.5 mm 이상 떨어뜨린다.
- 결합 edge의 2.8 mm 얇은 테두리 구간에는 M2 홀을 배치하지 않고, 하부 바닥판의 연속 지지 리브로 보강한다.

## 배열

KC2의 PCB 설계에서는 물리 배열과 firmware 동작을 분리해서 본다. 사용자 제공 KLE와 실물 측정은 switch center, key size, stabilizer 위치의 기준이고, ZMK keymap은 각 물리 키의 동작 기준이다.

무보강판 low-profile no-stabilizer 방향의 최종 split layout은 하위 문서 `docs/spec/20.kc2-no-stabilizer-layout.md`를 따른다. 이 하위 문서는 기존 `>=2u` 키를 모두 `2u` 미만의 물리 키로 분할한 77-key layout이며, 이 문서의 기존 71-key 배열 설명은 routed draft baseline으로 유지한다.

왼쪽 half 기준 물리 배열:

```text
Left half, 30 keys

Row 1: `  1  2  3  4  5  6
Row 2: Tab  Q  W  E  R  T
Row 3: Caps A  S  D  F  G
Row 4: Shift Z  X  C  V  B
Row 5: Ctrl Win Alt Fn Space
```

오른쪽 half 기준 물리 배열은 Keyboard Layout Editor raw data를 원본으로 둔다.

```js
[{x:0.5},"7","8","9","0","-","=",{w:2.25},"<-","DEL"],
["Y","U","I","O","P","[","]",{w:1.75},"\\",{a:7},""],
[{x:0.25,a:4},"H","J","K","L",":","\"",{w:2.5},"Enter",{a:7},""],
[{x:0.75,a:4},"N","M","<",">","?",{w:2},"Shift",{a:7},"",""],
[{x:0.75},"",{w:2},"","","","","","",""]
```

오른쪽 half KLE 해석:

```text
Right half, 41 keys

Row 1: x0.50  7  8  9  0  -  =  Backspace(2.25u)  Del
Row 2:        Y  U  I  O  P  [  ]  \(1.75u)        blank/Home
Row 3: x0.25  H  J  K  L  :  "  Enter(2.5u)       blank/PgUp
Row 4: x0.75  N  M  <  >  ?  Shift(2u)             blank/Up  blank/PgDn
Row 5: x0.75  blank/B_RH  Space(2u)  blank/RAlt  blank/Fn  blank/RCtrl  blank/Left  blank/Down  blank/Right
```

현재 ZMK 기본 레이어 동작:

```text
Row 1: `  1  2  3  4  5  6      |  7  8  9  0  -  =  BSPC  DEL
Row 2: Tab Q  W  E  R  T         |  Y  U  I  O  P  [  ]     \    Home
Row 3: Caps A S  D  F  G         |  H  J  K  L  ;  '  Enter PgUp
Row 4: Shift Z X  C  V  B        |  N  M  ,  .  /  RShift Up PgDn
Row 5: Ctrl GUI Alt Fn Space     |  B  Space RAlt Fn RCtrl Left Down Right
```

배열 제약:

- 왼쪽 half는 `~`부터 `6`, `QWERT`, `ASDFG`, `ZXCVB`를 포함한다.
- 오른쪽 half는 `7`부터 시작하며 `YUIOP`, `HJKL`, `NM`, punctuation, nav column을 포함한다.
- split 경계는 왼쪽 `B`와 오른쪽 `N` 사이의 성격을 유지한다.
- 오른쪽 하단 `B_RH`는 KLE 5번째 row의 첫 blank 1u key position이며, 오른쪽 Space 바로 왼쪽에 둔다.
- 오른쪽 Space는 KLE 기준 2u key다.
- 오른쪽 `Backspace`는 2.25u, `\`는 1.75u, `Enter`는 2.5u, `Shift`는 2u key다.
- 우측 끝 nav column은 오른쪽 PCB outline에 포함한다.
- 왼쪽 half의 가장 왼쪽 keycap edge는 키캡을 씌웠을 때 같은 X선에 정렬되어야 한다. 즉 첫 열 switch center는 단순 stagger 값이 아니라 각 key width의 절반만큼 보정한다.
- 왼쪽 bottom row는 사용자 제공 KLE 기준 `Ctrl Win Alt Fn Space`이다.
- PCB silkscreen은 keycap legend 기준인지 firmware 동작 기준인지 제작 전에 확정한다.

## 펌웨어 스펙

- ZMK shield id: `kc2`
- ZMK shield siblings: `kc2_left`, `kc2_right`
- board target: `nice_nano_v2`
- left build shield: `kc2_left`
- right build shield: `kc2_right`
- split central: left half
- layer 수: 3
  - `default_layer`
  - `fn_layer`
  - `fn_layer2`

주의:

- `fn_layer2` binding 수는 2026-06-02 검증에서 70개로 확인되어, 누락된 `&trans` 1개를 추가해 71개로 맞췄다.
- PCB 제작 전 `./zmk/app/build.sh`로 좌우 firmware 빌드를 검증한다.
- 기존 `kc1` 펌웨어 식별자는 KC1 핸드와이어링/이전 설계 기록을 가리키는 이름으로만 남기며, KC2 제작용 ZMK shield id로는 사용하지 않는다.

## Matrix

- logical rows: 5
- logical columns: 16
- mapped positions: 71
- transform row별 key 수: 15 / 15 / 14 / 14 / 13
- diode direction: `col2row`
- diode: 디바이스마트 상품번호 25 `1N4148`, SOD-27(DO-35), 75V, 450mA, 총 71개
- `col2row` 기준 diode의 cathode, 즉 표시선 쪽은 row net으로 둔다.
- diode 공간 확보가 현재 PCB 설계의 주요 리스크다.
- SOD-27(DO-35) 배치 공간이 실제로 부족하면 SMD diode로 전환한다.
- SMD 전환 1순위 후보는 `1N4148W` / `SOD-123`이다. 손납땜성과 공간 절약의 균형이 가장 좋다.
- SMD 전환 2순위 후보는 `1N4148WS` / `SOD-323`이다. 공간은 더 작지만 71개 수동 납땜 난도가 높으므로 SOD-123으로도 outline, M2 hole, routing이 성립하지 않을 때 사용한다.

## Left Half Matrix

왼쪽 half는 7 columns x 5 rows다.

| Net | nRF GPIO | Pro Micro/nice!nano pin 의미 |
| --- | --- | --- |
| L_COL0 | `gpio0 20` | D3 |
| L_COL1 | `gpio0 24` | D5 |
| L_COL2 | `gpio0 22` | D4/A6 |
| L_COL3 | `gpio1 0` | D6/A7 |
| L_COL4 | `gpio0 11` | D7 |
| L_COL5 | `gpio1 4` | D8/A8 |
| L_COL6 | `gpio1 6` | D9/A9 |
| L_ROW0 | `gpio0 9` | D10/A10 |
| L_ROW1 | `gpio0 10` | D16 |
| L_ROW2 | `gpio1 11` | D14 |
| L_ROW3 | `gpio1 13` | D15 |
| L_ROW4 | `gpio1 15` | D18/A0 |

## Right Half Matrix

오른쪽 half는 9 columns x 5 rows다. 오른쪽 local column 0..8은 global column 7..15에 대응한다.

| Net | Global col | nRF GPIO | Pro Micro/nice!nano pin 의미 |
| --- | --- | --- | --- |
| R_COL0 | G_COL7 | `gpio1 6` | D9/A9 |
| R_COL1 | G_COL8 | `gpio0 9` | D10/A10 |
| R_COL2 | G_COL9 | `gpio0 10` | D16 |
| R_COL3 | G_COL10 | `gpio1 11` | D14 |
| R_COL4 | G_COL11 | `gpio1 13` | D15 |
| R_COL5 | G_COL12 | `gpio1 15` | D18/A0 |
| R_COL6 | G_COL13 | `gpio0 2` | D19/A1 |
| R_COL7 | G_COL14 | `gpio0 31` | D21/A3 |
| R_COL8 | G_COL15 | `gpio0 29` | D20/A2 |
| R_ROW0 | - | `gpio0 20` | D3 |
| R_ROW1 | - | `gpio0 22` | D4/A6 |
| R_ROW2 | - | `gpio0 24` | D5 |
| R_ROW3 | - | `gpio0 17` | D2 |
| R_ROW4 | - | `gpio0 11` | D7 |

주의:

- 오른쪽 `R_COL7`과 `R_COL8`은 초기 draft의 D20/D21 배정에서 서로 교환했다.
- `R_COL7`은 `DEL`, `\`, `PgUp`, `PgDn`, `Right`가 포함된 긴 column이므로 controller 바깥쪽에 더 가까운 D21/A3에 배정한다.
- `R_COL8`은 `Home` 1키 column이므로 D20/A2에 배정한다.
- ZMK matrix pin 설정은 이 표를 기준으로 맞춘다.

## 전원 및 컨트롤러

- nice!nano v2를 Pro Micro 호환 24핀 socket으로 장착한다.
- socket은 디바이스마트 상품번호 5494 `싱글라운드소켓(64핀)`을 잘라 좌우 1x12 socket 2줄로 사용한다.
- nice!nano의 `B+`/`B-` top pins에는 socket/header를 설치하지 않는다.
- 각 half에 `TW301525` Li-Po 배터리 1개를 둔다.
- `TW301525`는 15 mm x 25 mm급이라 nice!nano v2 폭 18.3 mm 안쪽에 들어가기 쉽고, 이전 후보 `TW302030`보다 컨트롤러 아래 배치에 유리하다.
- `TW301525`의 80 mAh 용량은 nice!nano의 일반 권장 배터리 용량보다 작지만, 백라이트/RGB를 넣지 않는 전제로 유지한다.
- 배터리 출력단자는 `A1251-02`로 표기되어 있다.
- B+/B- pigtail과 A2506 PCB connector 2개 구조는 사용하지 않는다.
- X3 compact controller tab에서는 배터리 lead를 PCB가 아니라 nice!nano v2의 `B+`/`B-` pad에 직접 납땜한다.
- X3 carrier PCB에는 `BAT+`, `BAT-`, `NN_B+`, `NN_B-` solder pad와 이를 잇는 power trace를 만들지 않는다.
- 배터리 lead를 nice!nano v2에 직접 납땜하므로, controller를 socket에서 완전히 분리하려면 배터리 lead를 먼저 desolder해야 한다.
- 배터리 기본 `A1251-02` connector를 제거할 경우 한 선씩 절단/절연하고, 납땜 전 multimeter로 polarity를 실측한다.
- 전원 lead는 nice!nano v2 solder joint가 장력을 받지 않도록 wire loop, 접착 고정, 또는 하부 바닥판의 케이블 고정 구조를 사용한다.
- socketed nice!nano는 24핀 socket에서 분리할 수 있지만, 배터리 lead가 nice!nano v2 `B+`/`B-`에 직접 납땜되어 있으므로 완전 분리하려면 해당 lead를 desolder해야 한다.
- slide switch는 사용하지 않는다.
- slide switch와 전원 connector가 없으므로 일반 사용 중 hard power-off는 제공하지 않는다.
- 전원 차단이 필요한 정비 상황에서는 nice!nano v2에 직접 납땜된 배터리 lead를 desolder하거나 외부 배터리 lead 측에서 분리한다.
- 각 half에 프로그래밍용 tact switch 1개를 둔다.
- tact switch는 디바이스마트 상품번호 1322056 `NW3-A06-B3`를 사용한다.
- `NW3-A06-B3`는 SMD 부품이므로, 기존 6 mm THT tact switch보다 PCB 관통 구멍과 USB-C 아래 차지 면적을 줄이는 용도로 사용한다.
- 프로그래밍용 tact switch는 `RST`와 `GND` 사이에 연결하여 nice!nano bootloader/reset 진입에 사용한다.
- X3 carrier PCB에는 배터리/컨트롤러 전원 solder pad를 두지 않는다. 배터리 극성은 조립 전 multimeter와 nice!nano v2 `B+`/`B-` 표시로 확인한다.

## PCB 설계 제약

- 특정 키스위치 모델을 PCB 설계 기준으로 고정하지 않는다.
- switch footprint는 다중 호환 hole/pad pattern을 목표로 한다.
- 목표는 하나의 PCB에서 가능한 한 여러 switch family를 납땜할 수 있게 하는 것이다.
- 단일 hole pattern이 모든 제조사/모든 switch를 물리적으로 지원할 수는 없으므로, KiCad footprint 작성 전에 지원하려는 switch family별 pin pitch, metal pin, center/locator hole, keycap 간섭 치수를 라이브러리와 실물로 검증한다.
- `무보강판 스테빌라이저` 섹션의 적용 키에는 stabilizer footprint와 keepout을 포함한다.
- 보강판에 의존하는 plate-mounted stabilizer는 KC2 기본 구조와 맞지 않으므로 final footprint로 사용하지 않는다.
- 현 draft의 MX-style `KC2:PCB_Mount_2u_Stabilizer_NPTH`는 위치/공간 확인용 placeholder이며, low-profile 무보강판 실물 체결 검증 전에는 fabrication footprint로 사용하지 않는다.
- SOD-27(DO-35) 축형 1N4148 diode 71개를 배치할 공간이 충분한지 다중 호환 switch footprint와 동시에 검증한다.
- 이 다이오드는 through-hole axial 부품이므로 SMD diode보다 차지하는 면적과 lead bending 공간이 크다.
- DO-35 유지 실패 기준은 switch/stabilizer footprint와의 courtyard overlap, M2 hole 배치 실패, hole-to-hole clearance 위반, 결합 edge 2.5-3.0 mm 여백 침범, 하부 바닥판 지지점 간섭, lead bending 공간 부족 중 하나라도 발생하는 경우로 둔다.
- 공간이 부족하면 diode 위치 재배치, PCB 반대면 배치, routing 재배치를 먼저 검토하되, compact outline이나 M2 고정 홀을 훼손해야 한다면 SMD `1N4148W`/SOD-123 전환을 우선한다. SOD-123으로도 부족하면 `1N4148WS`/SOD-323을 검토한다.
- diode는 keycap, switch solder joint, controller socket, battery, M2 고정 홀, 하부 바닥판 지지점과 간섭하지 않아야 한다.
- hotswap socket은 기본 납땜형 KC2의 요구사항이 아니다. 단, 별도 산출물 `kc2_left-hotswap.*`, `kc2_right-hotswap.*`에서는 Kailh Choc/PG1350/PG1353 low-profile hot-swap socket 변형을 검토한다.
- hotswap 변형의 switch footprint는 `key-switches.pretty:SW_Kailh_Choc_V1V2_HotSwap_Hybrid`를 사용한다.
- hotswap 변형은 Kailh Choc V1/V2 low-profile socket, `CPG135001S30` 계열을 전제로 한다. MX 전용 Kailh hot-swap socket, 예: `CPG151101S11` 계열은 이 변형에 사용하지 않는다.
- hotswap socket은 bottom-side SMD pad를 갖는 부품이므로 PCB 하부면 soldering 방향, socket orientation, switch pin hole clearance를 1:1 출력물과 실물 소켓으로 확인한다.
- 무보강판 구조에서는 hotswap socket만으로 switch/keycap 흔들림과 이탈을 충분히 억제하지 못할 수 있다. 하부 바닥판, keycap, stabilizer, socket body 간섭을 test coupon으로 검증한 뒤 발주한다.
- `x1` 변형은 `hotswap` 변형을 복사한 hand-solder diode 개선판이다.
- `x1` 변형의 diode는 디바이스마트 상품번호 14592018 `1N4148W`, SOD-123을 사용한다.
- `x1` 변형의 diode footprint는 `kc2.pretty:D_SOD123_HandSolder_14592018`이며, KiCad 기본 `D_SOD-123`의 `0.9 mm x 1.2 mm` pad보다 큰 `1.4 mm x 1.55 mm` pad를 사용한다.
- `x1` 오른쪽 half는 enlarged diode pad를 쓴 autoroute의 board-edge clearance를 확보하기 위해 상단 outline에 0.3 mm relief를 둔다.
- `x2` 변형은 `x1`을 복사한 뒤 switch footprint를 `key-switches.pretty:SW_Kailh_Choc_V1_HotSwap_THT`로 바꾼다.
- `x2` 변형은 Kailh Choc V1/PG1350 기준으로 hot-swap socket pad와 through-hole 직접 납땜 pad를 모두 제공한다.
- `x2` 변형은 `x1`의 Choc V1/V2 hot-swap-only footprint를 유지하지 않는다. Choc V2까지 포함하는 socket+THT 통합 footprint는 현재 채택하지 않는다.
- `x2` 변형은 추가된 switch THT pad와 diode 간섭을 피하기 위해 diode y offset을 switch center 기준 `-7.6 mm`로 둔다.
- `x2` 오른쪽 half는 `x1`과 같은 상단 outline 0.3 mm relief를 유지한다.
- 현재 main PCB는 기존 `x3` 변형을 승격한 no-stabilizer layout 개선판이다.
- `x3` 변형은 switch footprint, diode footprint, diode y offset, 오른쪽 half 상단 outline relief를 `x2`와 동일하게 유지한다.
- `x3` 변형은 `docs/spec/20.kc2-no-stabilizer-layout.md`의 77-key layout을 사용하며, 물리 키 최대 폭은 `1.75u`이다.
- `x3` 변형은 `2u 이상` 키가 없으므로 stabilizer footprint를 생성하지 않는다.
- `x3` 오른쪽 half는 5개 row 모두 9개 matrix column을 사용한다. 기존 `R_COL8=D20`, `R_COL7=D21` pin mapping은 유지하되, firmware keymap에서는 duplicate legend physical key를 별도 위치로 구분해야 한다.
- `x3` outline은 증가한 matrix 밀도 때문에 양쪽 half의 inner edge에 `0.8 mm` routing relief를 추가한다.
- `x3` joined mechanical reference는 오른쪽 `Y`/`H` 돌출부를 왼쪽 `T`/`G` 홈으로 넣은 interlocked 배치에서 Edge.Cuts 간 최소 `1.0 mm` clearance를 유지한다. 오른쪽 `Y`/`H` 돌출부는 세로 inner Edge.Cuts 면을 `3.6 mm` margin으로 유지하고 가로 ledge만 `0.8 mm` 안쪽 relief 처리하되, 전기적 copper-to-edge clearance는 fabrication gate 기준을 계속 만족해야 한다.
- 상부 하우징이 없으므로 PCB outline은 손에 노출되는 최종 상부 외형이다.
- PCB 모서리는 라운드 처리한다.
- nice!nano는 각 half의 숫자열 바로 위에 가로 배치한다.
- controller는 키 배열 위쪽의 둥근 돌출 탭 안에 배치한다.
- controller 돌출 탭은 X 좌표상 결합 edge에 가까운 끝쪽으로 붙인다. 왼쪽 half에서는 오른쪽 끝, 오른쪽 half에서는 왼쪽 끝이 기준이다.
- 단, controller 돌출 탭은 결합 edge 최외곽까지 튀어나오면 안 된다. 결합/분리 시 탭이 먼저 닿지 않도록 왼쪽 half는 약 12 mm, 오른쪽 half는 약 17 mm 안쪽으로 recessed 처리한다.
- X3 compact controller tab은 기존 72.0 mm controller 탭보다 작게 줄이고, nominal 탭 폭은 54.0 mm 이하를 목표로 한다.
- X3 compact controller tab은 좌우 대칭 사각 탭이 아니라 USB-C/reset switch 쪽은 타이트하게, antenna keepout 쪽은 10 mm no-copper keepout을 포함하도록 비대칭으로 잡을 수 있다.
- 좌우 half를 붙였을 때 nice!nano의 USB-C 포트는 서로 반대쪽, 즉 바깥쪽을 바라보게 한다.
- 왼쪽 keyboard의 USB-C 포트는 왼쪽 바깥쪽을 향하게 한다.
- 오른쪽 keyboard의 USB-C 포트는 오른쪽 바깥쪽을 향하게 한다.
- 좌우 모두 nice!nano component side가 위를 향하는 top-side socket 배치로 두고, 단순 mirror가 아니라 회전 방향만 다르게 잡는다.
- 왼쪽 half는 USB-C가 왼쪽 바깥쪽을 향하고, antenna end는 오른쪽 결합 edge 쪽을 향한다.
- 오른쪽 half는 USB-C가 오른쪽 바깥쪽을 향하고, antenna end는 왼쪽 결합 edge 쪽을 향한다.
- KiCad 배치에는 `USB_OUT_LEFT`, `USB_OUT_RIGHT`, `ANTENNA_INWARD` silkscreen 또는 Dwgs.User 표시를 넣어 footprint 회전 오류를 검증한다.
- USB-C 포트 아래쪽은 각 half의 key-side, 즉 숫자열을 향한 쪽으로 정의한다. 프로그래밍용 tact switch는 USB-C 포트의 key-side 아래쪽에 상면 배치하며, 누를 수 있는 공간을 반드시 확보한다.
- 핸드와이어링 버전의 배열은 유지하되, PCB outline과 controller/USB 주변 외형은 PCB화에 맞춰 조정할 수 있다.
- USB는 nice!nano v2 자체 USB-C만 사용한다. 기존 USB-C guide/extension/외부 USB board 구조는 유지하지 않는다.
- USB-C 포트는 결합 상태와 분리 상태 모두에서 케이블을 꽂기 쉬운 방향으로 둔다.
- nice!nano의 USB-C 반대쪽 끝을 antenna end로 정의한다. KC2에서는 USB-C를 바깥쪽으로 향하게 하므로 antenna end는 좌우 결합 edge 쪽을 향한다.
- antenna end에서 최소 10 mm 길이, nice!nano 폭 전체, 그리고 인접 결합 edge 방향에는 copper pour, trace, via, battery, wire strain relief, M2 screw, 금속 insert, 금속 보강물을 두지 않는다.
- 이 keepout 값은 공식 pinout/schematic과 실물 측정 후 조정할 수 있으나, 1차 PCB 초안에서는 10 mm keepout을 기본값으로 둔다.
- 배터리를 controller 아래에 둘 수는 있지만, 안테나 바로 아래에는 두지 않는다.
- Li-Po pouch와 배선은 2.4 GHz 안테나를 detune하거나 감쇠시킬 수 있으므로, 배터리는 MCU/USB 쪽 아래로 치우치게 배치하고 안테나 아래는 비워 둔다.
- 프로그래밍용 tact switch는 USB-C에 더 가깝게 이동하되, top-side tact switch body와 bottom-side battery reference/하부 바닥판 고정 구조가 간섭하지 않도록 한다.
- controller와 tact switch는 손에 노출되는 상부 조건으로 배치하고, battery와 nice!nano 직접 납땜부는 하부 바닥판과 간섭하지 않게 배치한다.
- keycap 간섭, USB 삽입 간섭, 바닥면 쇼트 가능성을 1:1 출력물로 확인한다.

## 미확정 항목

- 다중 호환 switch hole/pad pattern 검증
- SOD-27(DO-35) axial 1N4148의 실제 배치 가능 여부
- 71개 diode의 실제 배치 가능 여부
- DO-35 유지, SOD-123 전환, SOD-323 전환 각각의 실제 배치 가능 여부
- SMD 전환 시 손납땜이면 SOD-123 우선, PCBA 또는 극한 compact 배치가 필요하면 SOD-323 허용
- keycap unit, 실제 keycap underside stem 간격, 무보강판에서 체결 가능한 PCB-mounted/PCB-retained stabilizer footprint
- stabilizer 1:1 출력물 또는 test coupon 기반 실물 끼움 테스트
- 실물 측정 기반 71개 switch center 좌표
- 좌우 PCB outline
- `TW301525` 배터리 위치와 하부 바닥판 고정 방식
- nice!nano v2 `B+`/`B-` 직접 납땜부의 service loop, strain relief, 절연 방식
- 전원 차단이 필요한 정비 상황에서 사용할 배터리 lead desolder 또는 외부 lead 분리 방식
- controller 아래 배터리 배치 시 antenna keepout 확보 방식
- `NW3-A06-B3` SMD tact switch의 key-side 상면 위치와 1:1 출력물 기반 조작 검증
- 하부 바닥판용 M2 고정 홀 위치
- M2 고정 홀을 둘 수 없는 영역의 접착 고정 방식
- 3D 프린터 하부 바닥판 형상과 PCB 지지점
- 결합 edge 하부를 지지하는 3D 프린터 바닥판 lip/rib 형상과 지지 위치
- 실리콘 feet 위치
- nice!nano 자체 USB-C 접근 방향과 cable clearance
- hotswap 변형의 Kailh Choc socket orientation, solder fillet 공간, socket body와 하부 바닥판 간섭

## 구매처 링크

| 용도 | 부품 | 구매처 |
| --- | --- | --- |
| Matrix diode | 디바이스마트 상품번호 25 `1N4148`, SOD-27(DO-35), 75V, 450mA | https://www.devicemart.co.kr/goods/view?no=25 |
| Matrix diode alternative 1 | 디바이스마트 상품번호 14592018 `1N4148W`, SOD-123 | https://www.devicemart.co.kr/goods/view?no=14592018 |
| Matrix diode alternative 2 | 디바이스마트 상품번호 15106773 `1N4148WS`, SOD-323 | https://www.devicemart.co.kr/goods/view?no=15106773 |
| Controller socket | 디바이스마트 상품번호 5494 `싱글라운드소켓(64핀)`, 2.54 mm pitch, 1열 round socket | https://www.devicemart.co.kr/goods/view?no=5494 |
| Battery | 디바이스마트 상품번호 1376800 `TW301525`, 3.7 V, 80 mAh, A1251-02, 15 mm x 25 mm급 | https://www.devicemart.co.kr/goods/view?no=1376800 |
| Programming tact switch | 디바이스마트 상품번호 1322056 `NW3-A06-B3`, SMD micro tact switch, 6.1 mm x 3.7 mm급 body, 2.55 mm급 높이 | https://www.devicemart.co.kr/goods/view?no=1322056 |
| Hot-swap socket variant | Kailh Choc/PG1350 low-profile hot-swap socket, `CPG135001S30` 계열. `-hotswap` 변형에서만 사용 | https://ko.aliexpress.com/item/1005009187521124.html |

Hot-swap 참고 자료:

- AliExpress mirror 조사: Kailh low-profile 1350 Chocolate switch용 hot-swap socket으로 표시됨. https://alitools.io/en/showcase/kailh-hot-swap-socket-for-low-profile-1350-chocolate-switches-on-mechanical-keyboard-pcb-socket-diy-base-modification-33023283633
- Kailh Choc hot-swap socket part number/source: `CPG135001S30`. https://www.flux.ai/whitelynx/kailh-choc-hot-swap-socket
- Kailh `CPG135001S30` datasheet mirror. https://jonathan.rico.live/projects/split-keyboard/files/kailh-choc-sockets.pdf
- `key-switches.pretty` compatibility table: `SW_Kailh_Choc_V1V2_HotSwap_Hybrid`는 Choc V1 조건부, Choc V2 compatible, Hot-Swap footprint로 분류됨. https://github.com/siderakb/key-switches.pretty
- Kailh-style hot-swap socket은 일반 switch footprint가 아니라 별도 footprint와 socket 방향 검증이 필요함. https://docs.keeb.supply/basics/soldering/hotswap/

## 폐기된 부품 후보

| 용도 | 부품 | 상태 | 링크 |
| --- | --- | --- | --- |
| Battery/controller harness | 디바이스마트 상품번호 10894399 `NW3-5264-02`, 2핀, 2.5 mm pitch, 약 200 mm, AWG26, A2506 한쪽 커넥터 | KC2 X3에서는 사용하지 않음. 배터리 lead를 nice!nano v2 `B+`/`B-`에 직접 납땜 | https://www.devicemart.co.kr/goods/view?no=10894399 |
| PCB power connector | 디바이스마트 상품번호 1357807 `NW-5268-2AW (2핀)`, A2506, Molex 5268 대응, 2.5 mm pitch, angle type | KC2 X3에서는 사용하지 않음. carrier-PCB 전원 connector/pad를 두지 않음 | https://www.devicemart.co.kr/goods/view?no=1357807 |
| Programming tact switch | 디바이스마트 상품번호 34555 `ITS-1105-5mm`, DIP tact switch, 높이 5.0 mm | USB-C 아래 공간이 커서 `NW3-A06-B3` SMD tact switch로 대체 | https://www.devicemart.co.kr/goods/view?no=34555 |
