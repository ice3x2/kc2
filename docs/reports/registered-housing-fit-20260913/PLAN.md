# 외벽 등록 및 이음부 조정 작업 계획

요구사항 원본: docs/spec/10.product-architecture.srs.md의 CON-ARCH-006 최신 사용자 개정. 서비스 보호는 CON-ARCH-007, canonical 게시 정책은 OPS-ARCH-006. 이 문서는 실행 계획이며 별도 요구사항 원본이 아니다.

최종 상태(2026-09-14): 아래는 시간순 작업 이력이다. 35 CAD canonical 게시 및 사후 검사, 최종 70개 모듈/356개 시험, `.codex-tmp` 없는 516파일 격리 검증이 모두 통과했다. 16개 PCB/Gerber는 보존됐다. 최종 결과와 실제 증거 연결은 [README](README.md) 및 [게시 확인 기록](publication-confirmation.json)을 따른다. 실물 적합성은 여전히 미검증이며 아래 중간 단계의 대기/실패를 최종 상태로 오인하지 않는다.

## 기준과 목표

기준 Git: 5b99bcb4567ea1c6bb4f17e54887d4de7614cd03. 시작 worktree는 clean이었다. 기존 publication은 21개 upper CAD, 14개 lower CAD와 주문된 PCB/Gerber 16개를 포함한다. 이전 설계는 Git 이력으로 보존하며 canonical CAD는 새 검증 완료 전 덮어쓰지 않는다.

1. PCB는 Z2.50 받침에 놓이고 상단은 Z4.10이다. 새 외벽은 PCB를 여유 있게 감싸고 상판 아래 홈에 들어가 XY 등록을 돕되 기존 높이/나사 하중 경로를 유지한다.
2. 중앙 좌우 키보드 사이에는 상하 등록 홈을 생략한다. 외벽 끝은 숨기거나 부드럽게 끝내어 외관을 유지한다. 기존 joined transform dx124.625,dy0과 키 간격을 바꾸지 않는다.
3. 중앙 결합은 현재 비접촉이다. 전체 외곽을 가까이 이동시키는 방식이 아니라 분리 가능한 국소 안내/마찰부를 설계한다. 단순 gap 감소를 마찰 검증으로 대체하지 않는다. 의도적 접촉의 변형과 삽입 경로를 검사한다.
4. 오른쪽 A/B는 반대로 기존 약0.20 mm 간격을 늘린다. 새 부품은 중앙과 다른 공차 매개변수를 사용하며 요철 외의 나사/스위치 위치나 전체 축척을 바꾸지 않는다.
5. MX/Choc V1/Deep Sea Mini 상판, 일반/magnetic 하판 모두 새 형상과 맞아야 한다. 주문된 PCB와 Gerber는 변경하지 않는다.

## 순서와 산출물

- [x] 현행 SRS/active target/진행 및 완료 요약 확인, 사용자 승인 변경을 SpecKiwi로 CON-ARCH-006에 기록.
- [ ] 형상 조사: 기존 actual STEP/보고서 단면과 PCB/부품 보호 공간에서 벽/홈, 중앙 안내부, A/B 변경의 실제 위치를 선정. 치수는 시험 초기값과 실제 측정값을 구분.
- [ ] TDD: 중앙과 A/B 공차 혼동, PCB/부품 침범, 얇은 잔여벽, 분할 연결/단절, 등록 홈 누락을 실패시키는 시험부터 작성.
- [ ] 구현: 새 매개변수/생성기에서 하판과 세 상판을 변경. 기존 source-bound 생성기/보고서는 변경하지 않고 과거 증거로 유지.
- [ ] 실제 STEP/STL 검사: 형상 델타, 부품 공간, 나사/지지 높이, 외벽/홈 간격, 중앙 삽입 경로와 의도 접촉, A/B 간격 및 조립 경로, 연결체,150 mm 크기, 출력 지지.
- [ ] 서브에이전트 독립 검증. 지적 사항을 수정하고 해당 실패 회귀시험과 전체 관련 검사를 재실행. 완료 기준을 낮추어 통과시키지 않는다.
- [ ] 실제 Fusion F3D 생성/재열기/STEP readback 검사와 소스 고정 검증.
- [ ] canonical hardware/MODELS 게시 및 인쇄/조립 안내. 출력 시험편으로 공차 확인 방법과 물리 미검증 항목을 명시.

## 초기 공학 검토값 (확정 형상 아님)

A/B 기본 상대 여유0.40 mm를 첫 후보로 사용한다(이전 약0.20). 진입부는 추가0.20 mm/높이0.40 mm 완화 후보이며 부품/지지 보호 실패 시 배치 재검토가 필요하다. 상하 등록은 한쪽0.20~0.30 mm, 홈 천장 여유0.20~0.30 mm부터 검토한다. 기존1.20 mm 벽에 홈을 그대로 파지 않고 충분한 솔리드 영역을 사용한다. 저상형의 낮은 높이에서는 깊이를 MX와 별도로 판단한다.

기존 중앙 전체 투영 최소 간격은 MX0.445999 mm, 저상형1.299998 mm이다. 이 숫자는 전체 외곽 최솟값이지 중앙 안내부 배치 위치의 사용 가능한 폭이 아니다. 기존 자석 부근의 더 넓은 국소 공간과 부품 보호 공간을 별도로 확인한다.

## 증거의 한계

사용자 보고는 구형 A/B 과도한 끼움과 중앙 헐거움의 실물 피드백이다. 새 설계의 마찰력, 손 감촉, 재료 변형/피로, 전체 키캡 이동, 실제 공급 부품/납땜 편차는 디지털 결과만으로 검증 완료 처리하지 않는다. 별도 공차 시험편/실제 재출력 확인이 필요하다. PCB 새 발주나 구매는 이 작업에 포함되지 않는다.

## 1차 구현 및 독립 검토 (진행 중)

순수 형상 계획 모듈 세 개를 추가했다: kc2_central_fit, kc2_split_fit_relief, kc2_wall_registration. 최초28시험은 통과했지만 이는 최종 CAD가 아니다. 독립 검토에서 최소 홈 engagement 누락, 중앙 contact 삭제를 통과시키는 검사, bool 치수 입력, 연결된 상태로도 얇아질 수 있는 A/B 뿌리 문제가 발견되었다. 실패 회귀시험 후 앞의 세 문제를 수정했고 뿌리는 실제 보호 도형을 명시하는 보완을 진행한다.

실제 오른쪽 upper domain/mask의 A/B 간격0.199759 mm는 core 계획에서0.400010 mm로 증가했다. 진입부0.600007 mm 후보는 [76.0,111.75] 나사 보스 반경2.30 보호 영역0.000740 mm²를 침범하므로 무조건 적용하지 않는다. 높이별 보호 공간으로 재계산하거나 해당 추가 진입 완화값을 줄여야 한다.

중앙 안내부 후보는 local Y95/117, 원래 자석 Y103/111을 피한4.00 mm 국소 틈이다. 각측2.80 mm 돌출로1.60 mm 맞물림, 폭2.40 mm 혀와 양측0.15 mm 주행 여유, 명목0.02 mm 탄성 접촉 후보를 순수 단면으로 검토했다. 현재 접촉 스트립은 rigid cheek와 붙어 있어 그대로 압출하면 독립 탄성부가 되지 않는다. lateral relief/고정 뿌리/실제 Z 구조가 없는 상태이며 compliance_verified=false이다. 이 후보를 최종 하우징으로 게시해서는 안 된다.

실제 현행 upper 단면 Z4.40..6.20의 교집합을 사용한 보수적 외부 registrar 배치 조사에서, upper 재료를1.45 mm 안쪽으로 줄이고 PCB+.30 영역을 뺀 가용 영역은 좌우/세종류 모두0 mm²였다. 이는 '기존 외벽에 폐쇄 홈을 깎기만 하는 방식'의 공간 부족을 보여주며 전체 등록 구조 불가능을 뜻하지 않는다. 다음 단계는 중앙 제외 구간의 국소 강성 리베이트/단차 또는 PCB 위 비접촉 높이로 들어오는 지지된 등록부를 검토하고, 변경량/키캡/부품/출력 지지를 실제 CAD로 증명하는 것이다. 단순히 잔여벽 기준을 낮춰 이전 파손 문제를 재현하지 않는다.

아직 canonical STL/STEP/F3D, PCB/Gerber는 변경하지 않았다. 새 CAD 생성, 반복 독립 CAD 검토, native 검증 및 게시가 남아 있다.

1차 수정 후 순수 계획 시험33개 통과(중앙8/A-B11/등록14). A/B에는 이름 붙은 RequiredRoot 보호 도형이 추가되어 원래 존재 여부와 core/entry 양쪽 잔존을 확인한다. SRS validate는0오류/0경고이며 기존 canonical publication 검사도21출력/30보존파일/124바인딩 통과했다. 이는 기존 배포물이 손상되지 않았다는 증거이지 새 하우징 완성 증거가 아니다.

## 2차 실제 형상 진행과 사용자 선택 대기

중앙 접촉부는 기존 rigid cheek에 붙은 얇은 스트립 대신 cheek 자체를 바닥에만 연결된 짧은 탄성벽으로 변경했다. 외측0.30/케이스측끝0.80 mm 빈 공간을 둔다. 실제 두 국소 BRep의 접촉은 최상단Z1.40..1.50에만 생기며 명목0.02 mm이다. 실제 부품 보호 공간으로 뿌리 추가물을 절삭한 좌우/Y95,117의4개 STEP/STL을 .codex-tmp/registered-housing-fit/central에 생성하고 STEP 재열기/메시/보호공간/기존 외곽의 변형 공간 침범 없음 검사를 통과했다. 하판 전체 융합, 실제 강도/힘, native 검증은 아직 아니다.

외측 개방 registrar는 각측3개 고정위치의 계획 및8시험(실제 PCB/6프로파일 포함)이 통과했다. 최대1.60 mm 국소 외곽 확장을 포함한 초기 치수는 SpecKiwi로 CON-ARCH-006에 기록했다. 아직 전체 둘레 가림벽이나 실제 A/B 분할을 포함한 최종 CAD 검증은 아니다.

A/B 단순 절삭은 기존 저상형에서0.540242 mm였던 일부 개구 지지폭을0.440120 mm로 줄이는 문제가 있어 게시 대상이 아니다. 실제 STEP 절삭 진단 작업은 실행 중이며 별도 진단 파일만 쓴다. 새 profile-aware 분할 계획은 실제14.20 개구와0.60보호링,Ø4.60보스,0.40 mm 간격을 사용하고15도 단위 검색으로 기존Ø4.50 head/2.00neck 요철2개를 유지하는 안을 찾았다. 실제 모델 생성과 독립검증이 필요하다.

후속 정정: profile-aware 초기 후보 두 개는 보호링과 간격을 만족해도-X방향 이탈이 가능하다는 강화 회귀시험에 실패했다. 따라서 위의 '안'은 채택/검증 완료가 아니다. 각 요철이 모든 방향을 단독 차단하도록 요구하는 과도한 제한 대신 두 후보가 상호 보완하여 전체 부품의 이동을 막는지 검사하는 조합 탐색으로 수정 중이다. 이미 지지폭 부족이 확인된 단순 절삭 진단 PID32140의 계속 실행은 유효한 최종 설계에 기여하지 않으므로 명령줄을 확인한 해당 작업만 중단하도록 요청했다. 부분A의 계산 결과를 전체 STEP 검증으로 확대하지 않으며 실패안을 재시작하지 않는다.

### 전체 중앙 상승벽의 공간 충돌 — 아래 최신 승인으로 해결

actual 고정 좌우 PCB의 최소 간격은1.10 mm이다. 세계XY 점쌍(161.625,86.5)-(161.625,87.6) 및(168.1125,125.7)-(168.1125,124.6)에서 확인됐다. 또(159.8675,106.97)-(160.571595,105.327112)의 간격은1.787409 mm이다. 양측PCB여유0.30을 빼면 최소구간의 총 재료 가능폭은0.50 mm뿐이어서 양측1.20벽이나 공유1.20벽 모두 불가능하다.

전체1.20 ring의 actualjoined 교차면적은14.840701 mm²이고3영역(worldXY): [158.450191,86.1,166.524809,88.0], [158.450191,105.15,161.762309,107.05], [163.212691,124.2,171.287309,126.1]. PCBZ2.50..4.10 공통밴드이므로 위아래 엇갈림만으로 해결되지 않는다. 전체벽과MX몸체교차(left0.605018/right1.210034 mm²)도상부밴드에서 보호해야 한다.

사용자에게 이3구간만 새PCB감싸는 상승벽을 생략하고 기존 소켓 가림을 유지해도 되는지 비동기 질문을 보냈다. 승인 전 중앙 생략/박벽/PCB위치변경을 구현하지 않는다. 대안은 새구조재검토이며 아직 전체완료나 최종인쇄파일 교체를 주장하지 않는다. 이 결정은 기존 중앙 홈 생략 승인과 다른 범위이다.

### 최신 사용자 승인 및 실제 CAD 진행

사용자는 기존 소켓 가림벽 유지와 중앙 외벽 예외를 승인했다. CON-ARCH-006에 SpecKiwi로 기록했다. 위 승인 대기 문단은 이전 경과이며 현재 승인 장애물이 아니다. 세 영역에 1.20 mm 둥근 종료 여유만 더해 새 상승벽을 국소 생략하며 기존 소켓 가림벽은 절삭하지 않는다. 수정된 전체 외벽 계획의 좌우 간격은0.80 mm, 겹침0이다. 각측 제거면적31.669171 mm², 서비스 개방면적17.04 mm²이며 세 국소 구간에서는 PCB 가장자리를 새 벽이 완전히 둘러싸지 않는 예외가 남는다.

왼쪽 Deep Sea 상판의 실제 STEP/STL 생성과 STEP 재열기가 완료되었다. 독립 실제 전체 단면 검사가 진행 중이다. 왼쪽 일반/자석 하판도 실제1솔리드, 기존 재료 손실0, 계획 밖 추가0, STEP 재열기 및 닫힌 STL 검사를 통과했다. 완전한 부품/자석 공간과 조립/인쇄 검증은 별도 진행 중이며 아직 최종 게시하지 않는다.

오른쪽 상판의 초기 Ø4.50 머리 후보는 채택하지 않는다. 국소 스위치 링 소유권을 조정하고 머리 Ø4.00/목2.00으로 변경한 후 세 프로파일 계획이 0.40 간격,0.60 스위치 링,Ø4.60 나사 보스,두 요철의 네 방향 이탈 방지 시험을 통과했다. Ø4.00/0.40 조합의 명목 걸림폭은 한쪽0.60 mm이며 이전 Ø4.50 후보의0.85보다 작다. 실제 CAD와 조립 검증이 남고 강도·손 감촉은 출력 전 미검증이다.

### 통합 검토에서 발견한 문제와 후속 수정

일반 상승벽 상단 Z4.35와 상판 밑면 Z4.40 사이에는 실제 STL에서도0.0500002 mm밖에 여유가 없었다. 일반 벽을 Z4.10으로 낮춰0.30 mm를 확보하고 위치맞춤 돌기는 Z5.00 그대로 유지하도록 CON-ARCH-006을 개정했다. 왼쪽 무자석/자석 하판의 수정 STEP/STL은 생성 완료했다. 무자석 실제 제거량141.732557 mm³, 계획 밖 삭제/추가0이며 이전4.35 mm 하판의 native 결과는 현행 증거가 아니다. STEP의 겹친 작은 경계를 직접 절삭한 첫 시도는 커널 유효성 검사에 실패해 게시하지 않았고, 전체 수평 절단 후 실제 등록 돌기 부분을 유지하는 방식으로 수정하여 통과했다.

새 오른쪽 외벽과 바닥은 중앙 탄성부의 자유 공간과 혀의 접근 경로를 일부 침범했다. 기존 가림벽은 유지하고 새 추가물에만 측면·상단0.30 mm와 직선 삽입 경로 여유를 주었다. 이로 인해 중앙 두 곳에 길이5.70 mm의 짧은 브리지가 생긴다. 이는 의도한 국소 공간이며 지지 없는 출력 성공을 실측 통과로 표시하지 않는다. 브리지·탄성부·끼움 감촉은 실제 인쇄 확인이 필요하다.

오른쪽 하판은 수컷 목2.00/머리4.50 mm를 줄이지 않고 암컷만 확장한다. 실제 평면 간격0.400031 mm,목 약2.80 mm,걸림폭 약0.85 mm 후보를 사용한다. 두 연결 위치,네 방향 걸림 및 주변 받침/레일 유지 계획 시험이 통과했으나 실제 전체 하판 검증은 아직 남아 있다.

왼쪽 세 종류 상판의 생성 및 실제 STL 전체 단면 검사는 통과했다. Deep Sea는 실제 STEP 전체 단면 검사와 Fusion 생성/재열기도 완료했지만 native readback 독립 형상 검증은 별도 진행 중이다. 나머지 실제 STEP 및 오른쪽 생성·검증을 진행한다.

전체 키보드 접근 경로는 PCB/새 외벽/바닥/등록부/세 상판을 포함한 보수적 평면 envelope로 정확한 X-7.8..0 이동 합집합을 검사했다. 중앙 별도 검증 구역 밖 최소 간격은 MX0.446 mm/저상형0.503908 mm로 통과했다. 이 보고서는 계획 envelope 증거이며 최종 actual CAD의 해당 envelope 포함 및 중앙 actual 검증이 함께 통과해야 최종 조립 증거가 된다.

### 최신 사용자 범위 정정 — 실리콘 발 보류

사용자가 “실리콘 발은 아직 신경쓰지마”라고 지시했다. 실리콘 발의 위치/접착 면적/지지 다각형/무게중심 검토는 중단하고 이번 완료 조건에서 제외한다. 기존 바닥은 유지하며 연속성·두께·출력성과 부품 간섭 검증은 계속한다. 실리콘 발이 검증됐다는 의미는 아니며 발 관련 새 배치나 파일은 게시하지 않는다. CON-ARCH-006에 해당 보류를 기록했다.

### 최신 실제 검증 진행

왼쪽 MX/V1/Deep Sea 상판은 실제 STEP 전체 단면, STL 전체 단면, Fusion 저장·재열기와 native readback 독립 전체 단면 검사를 모두 통과했다. 오른쪽 세 상판의 생성 및 STL 단면 검사도 통과했으며 실제 STEP·분할 구조와 native 검사는 진행 중이다. 아직 canonical 게시 완료를 의미하지 않는다.

하판 전체를 기존 명목0.35 mm 제작용 절삭 영역과 비교한 첫 검사는27.356211 mm³ 침범으로 실패했다. 별도 진단에서 이전 canonical 하판도 동일한27.356211 mm³이고, 이는 기존 지지면의0.02 mm 평면 단순화와 정확히 일치했다. 실제 원시 부품의 필수0.30 mm 여유 및 Z−0.40..2.50을 적용한8개 부품 종류의 현재 왼쪽 무자석 하판 실제 침범은 모두0이었다. 새 추가물의 제작용0.35 보호와 전체 형상의 필수0.30 보호를 분리하여 검사하며 최초 실패를 삭제하거나 실제 부품 간섭을 허용하는 방식으로 해결하지 않는다.

자석형은 새 외벽이 기존 홈 입구를 가리는 문제가 발견되어 수정 중이다. 기존 Ø2.40×깊이1.20 mm 블라인드 홈과 뒷벽은 유지하고 새 외벽만 관통하는 동축 Ø2.40 mm 삽입 통로를 추가한다. 바깥 입구에서 기존 홈 뒷면까지는2.80 mm이며 기존 홈 자체의 깊이와 다르다. 자석 없는 버전에는 통로를 만들지 않는다. 외부부터 실제 자석이 들어갈 경로, 바닥 잔여부와 원래 홈 보존을 별도로 검사한다.

후속 실제 결과: 왼쪽 자석형 통로 수정과 독립 STEP 삽입로 검사가 통과했다. Y103/Y111의 경로 막힘, 기존 포켓 막힘,0.60 mm 뒷벽 및 주변 재료 누락은 모두0이다. 새 벽에서 각5.428672 mm³만 제거했고, 총 자석 빈 공간21.714688 mm³가 독립 기대값과 일치했다.35개 소스 바인딩을 재검증했다. 실제 끼움과 오른쪽/native 검증까지 통과했다는 의미는 아니다.

오른쪽 무자석 하판의 생성·단일 부품/닫힌 메시 검사도 통과했다. 실제 A/B 최소 간격0.400031 mm, 기존 목2.00/머리4.50 유지, 계획 밖 받침 손실0 및 중앙 운동 공간 침범0이다. 독립 하판 검사와 자석형 생성은 이어서 진행한다.

오른쪽 MX 실제 분할 검사는0.400031 mm 최소 간격과 스위치 링·나사 보스·네 방향 이탈 방지 조건을 통과했다. 별도 전체 재료 검사의 최초 실패는 잘못 적용된 두 seam 조건이었다. 낮은 층의 부품 보호 공간은 상대편 재료를 없앨 수 있고, 요철 모서리에는 명목 슬롯0.40과 달리 국소0.52494 mm 틈이 있다. 실패 기록을 보존하고 현재 실제 전체 단면 증거 및 독립 재계산 분할 마스크를 결합한 별도 검증을 추가했다. 각 분할 마스크와 교차한 독립 필수 재료에 누락0, 실제 단면 오차까지 합한 최대 누락2.575e-7/추가2.016e-7 mm²로0.001 mm² 이내였다. 허용 틈 숫자만 늘리거나 누락 영역을 숨긴 것이 아니다. MX Fusion 저장·재열기는 완료됐으며 native readback 독립 검사는 아직 별도 진행 대상이다.

후속 진행: 오른쪽 MX native 독립 전체 단면 검사가 통과했다. 오른쪽 V1도 실제 분할 및 독립 필수 마스크 기준 직접 STEP 검사가 통과했다. 모든 상판6종의 Fusion 저장·재열기는 완료됐고 V1/Deep Sea의 native 독립 검사는 남아 있다. Deep Sea의 분할·직접 STEP 검사는 아직 미실행이다.

모든 하판4종의 최종 STEP/STL 생성이 완료됐다. 오른쪽 자석형은 무자석 실제 형상에서 기존 블라인드 홈과 새 삽입 통로만 제거했다. 총 제거21.714688 mm³, 계획 밖 제거/추가/기존 자석형 재료 손실0, 두 솔리드, 최소 A/B 간격0.400031 mm로 생성 검사를 통과했다.

왼쪽 하판의 독립 void v2 종합 검사가 통과했다. 무자석/자석 모두 필수 부품 여유·새 재료의 명목 여유·나사·필수 외벽/바닥/등록부·상판 아래0.30 mm 공간·원래 하판 보존 항목의 침범/누락은0이다. 원래 자석 빈 공간10.857344 mm³와 통로 추가 후21.714688 mm³의 관계도 실제 형상으로 확인했다. 왼쪽 무자석 실제 바닥은1.20 mm 일정 두께의 연속 Polygon, 면적13959.266947 mm², 내부 관통 구멍0이며 실제 STL은 닫힌 양의 한 셸로 확인했다. 실리콘 발 배치/접착 검사와는 무관하다.

추가 검증 방법으로 하판 native 형상에 대한 엄격한 동일 재료 증거 연결을 준비했다. 실제 원본 STEP과 native readback의 각 대응 솔리드에서 양방향 재료 차이를 커널로 계산한 값이 모두 정확히0이고 모든 파일/생성/실행 코드 바인딩이 일치할 때에만 이미 통과한 source 바닥·분할·void·자석 경로 성질을 연결한다. 기존0.002 mm³ 허용치 안이라도 차이가0이 아니면 이 방법은 거부하고 직접 native 검사를 사용한다. source 기능 검사는 생략하지 않는다. 파생 보고서는 native 검사를 다시 실행했다고 표시하지 않으며 실제 출력/강도/감촉 검증도 아니다. 아직 실제 하판 native 동일 재료 결과나 파생 보고서는 생성되지 않았다.

자석 거리의 의미를 구분한다. 기존 홈 입구의 세계 X좌표170.0125/174.0125는4.00 mm 떨어져 있다. 깊이1.20 mm 홈에 두께1.00 mm 자석을 완전히 안착시키면 각 면은0.20 mm 안쪽으로 들어가므로 자석 작동면 간 명목 간격은4.40 mm이다. 새 외벽 간0.80 mm는 자석 면 간격이 아니며 흡착력 개선 증거도 아니다. 접착층과 실제 부품 편차, 자력은 물리 확인 대상이고 자석을 새 외벽 통로로 옮기는 변경은 하지 않는다.

Deep Sea 오른쪽 실제 분할 검사도 최소 간격0.400031 mm, 두 연결부/스위치 링/나사 보스/네 방향 걸림 조건으로 통과했다. 직접 전체 STEP 재료 검사와 남은 native 독립 검사는 계속 진행한다.

현재 코드의46개 핵심 회귀 모듈에서220개 시험을177.065초에 실행하여 모두 통과했다. 이는 중간 회귀 실행이며 아직 미완료인 실제 형상 보고서를 포함하는 최종 source-bound test-execution 증거를 대신하지 않는다. 게시 직전에 전체 필수 실제 보고서와 안내문을 고정한 실행이 별도로 필요하다. 재생성 순서와 보존 입력, 기준 Git CAD를 격리 worktree에서 사용하는 주의사항은 REPRODUCE.md에 기록했다.

후속 상판 결과: 오른쪽 Deep Sea 직접 STEP 전체 재료 검사와 오른쪽 V1 native 전체 단면 검사가 통과했다. 여섯 상판의 source STEP/STL은 모두 통과했고 Deep Sea 오른쪽 native만 진행 중이다.

오른쪽 무자석 하판의 독립 분할 검사는 수용부 목 계산 항목으로 실패했다. 실제 최소 간격0.400031 mm, 두 수컷 목2.00/머리4.50의 재료 누락0, 네 방향 걸림 및 두 바닥 연결성은 통과했다. 별도 실제 선분/단면 진단에서 Y73.25는 주변 빈 공간을 합산한 잘못된 폭 계산이 포함되었으나, Y86.25에는 실제 위쪽 돌출부의 얇은 끝도 존재했다. Z0 단면에서 첫 수용부의 작은 삼각형은 별도 Polygon 약1.06935 mm²로 바닥에만 연결된다. 따라서 단순 계산 수정만으로 승인하지 않고 두 수용부의 상부 얇은 부분 정리와 바닥 결합부 보존을 검토한다. 기존 .60 mm 리드 하부 여유를 줄이는 보강은 채택하지 않는다. 실패와 진단 자료를 보존하며 현재 오른쪽 하판은 게시 대기 상태이다.

왼쪽 일반/자석 하판은 각각 source STEP와 Fusion native readback의 실제 양방향 재료 차이가 모두 정확히0으로 통과했다. 자석형 바닥도1.20 mm 일정 두께/연결성/내부 관통 구멍0 및 닫힌 단일 STL 검사를 통과했다. 이 실제 동일 재료 증거에 한해 두 바닥·왼쪽 void·자석 입구의 source 검증을 native에 연결하는 보고서를 생성한다. 이는 native 기능 검사를 다시 실행했다는 뜻이나 물리 강도/실리콘 발 검증이 아니다.

### 검증 재개 — 오른쪽 D8 판정 불일치 (CON-ARCH-006)

여섯 상판의 STEP/STL/native 독립 보고서가 모두 통과 상태이고, 왼쪽의 두 바닥·void·자석 입구 native 동일 재료 연결 보고서도 생성되었다. 오른쪽은 최종 승인하지 않는다. 원래 void v2는 정상/자석 모두 부품 보호 공간 침범46.794929654225015 mm³로 실패했으며 원본 보고서를 보존한다. 개별 다이오드 검사39곳은0이었으나, 원래 합집합에서 추출한32개 다이오드 도구와 두 하판 솔리드의64쌍 재현에서는 D8 위치의 tool2/partA 한 쌍이 같은 전체 도구 체적을 반환했다. 나머지63쌍은0이었다.

새 STEP와 새 D8 도구만 사용하는 비파괴 Common 진단에서도 교차체적46.794929654225015 mm³가 재현됐다. 연산 전후 실제 솔리드 거리 모두0, InnerSolution=true이며 도구 중심은 하판 외부로 분류된다. 따라서 이 단일 진단의 실패 원인을 앞선 Boolean 연산의 입력 변경으로 설명할 수 없다. 실제 간섭인지 점/형상 분류의 수치적 문제인지 아직 확정하지 않았으며, 국소 경계 거리와 점 분류를 추가 확인한다. 이 결과를 통과로 바꾸거나 인쇄 승인 근거로 사용하지 않는다. 관련 거리·수용부 보호 회귀시험23개는 재실행 통과했으나 실제 오른쪽 하판 합격을 대신하지 않는다. canonical 모델과 주문된 PCB/거버는 변경하지 않았다.

후속 D8 국소 증거: 내부로 분류된 정점에서 실제 shell/face까지0.042551974542 mm 떨어져 있으며 Y±0.00001 mm에서 외부로 판정이 바뀐다. 실제 STEP 단면 Z−0.40001/−0.4/−0.39999/0의 도구 겹침은 모두0이다. 전체 D8 닫힌 shell과 하판 닫힌 shell 간 거리는0.024768146295 mm이고, 도구 중심은 실제 단면 및 solid classifier 모두 외부다. 도구 전체를 포함하는 국소 ROI는 전 면이 수평/수직 PLANE이며 중간 Z전이가 없고, 단면×높이 부피 오차9.4387431e−8 mm³이다. 따라서 해당 D8 결과는 실제 국소 간섭이 아닌 solid 내부 분류의 수치 불일치를 뒷받침한다. 원래 실패와 세 진단은 보존하며 다른 부품/자석형 전체 검사나 오른쪽 수용부 수정의 승인으로 확대하지 않는다.

상판21개 검증 보고서의539개 source 해시(96개 고유 파일)를 재확인하여 불일치0을 확인했다. 새 검사 코드의 Git 줄바꿈 보존 시험은 실패를 먼저 확인한 뒤 .gitattributes 범위를 보완하여2개 모두 통과했다. 정상/자석 전체 부품 거리와 필요한 국소 독립 증거의 결합 검증은 후속 진행 대상이다.

왼쪽 하판10개 보고서의514개 해시(76개 고유 파일)도 불일치0을 확인했다. 신규 국소 인증6개와 별도 predicate bundle7개 시험은 통과했다. 이들은 전체612쌍/153개 보호 솔리드, 원래 실패값 보존, 정확한 D8 예외 범위와 실제 닫힌 경계·ROI 증거를 검증하는 도구이며 실제 최종 보고서는 아직 아니다. 바닥 전용 수용부 검사기도 작은 CAD 시험3개가 통과했고 실제 하판에는 아직 실행하지 않았다.

전체 거리 검사의 첫 실행은 약15분간 단일 코어 계산 중 예상 D8 실패까지 관찰했으나 끝나지 않았다. 해당 KC2 Python 프로세스의 정확한 명령줄을 확인하여 그 프로세스만 종료하고 원래 코드3개와 해시·관측 출력을 lower-development/component-distance-attempt-1에 interrupted_not_accepted로 보존했다. 두 형상을 받는 생성자와 후속 Perform이 계산을 중복 실행하던 경로를 기본 생성자→형상 입력→병렬 설정→Perform1회로 변경했다. 호출 순서의 실패 시험 후 기존 포함/접촉/유한성 시험을 유지해 거리8개와 국소 인증6개가 통과했다. 보호 형상·검사612쌍·여유 수치는 바꾸지 않았으며 새 코드 바인딩으로 전체 검사를 다시 실행 중이다. 첫 미완료 실행을 합격 증거로 사용하지 않는다.

### 2026-09-14 실제 전체 높이 구간 검증 (CON-ARCH-006, OPS-ARCH-006)

오른쪽 무자석 하판의 `lower/right-normal-strata-review.json` 실제 검사가 통과했다. 전체 STEP의 두 닫힌 양의 솔리드와 잔여 면/선/점 부재를 확인하고, 보호 공간 Z−0.4..2.5의 실제 경계가 수평/수직 평면 또는 정확히 식별한 수직 나사 파일럿 원통9개로만 구성됨을 검사했다. 전체 전이 높이12개 사이의11개 일정 단면 구간과12개 경계면 폐포 모두153개 부품 보호 영역과 겹침0, 최소 보수적 XY 간격0.0231417095415169 mm로 통과했다. 파일럿 안쪽 빈 공간은 보수적으로 재료에 포함하여 검사했으며 임의 높이 표본만으로 전체를 추정한 검사가 아니다. 원본 실패의46.794929654225015 mm³ 수치는 보존하고 새 Boolean 교차체적0을 만들어 기록하지 않았다. 원본 보고서와 생성물/실행 코드48개 바인딩 모두 현재 파일과 일치했다.

이 결과는 무자석 하판의 부품 보호 공간에 한정된다. 자석형의 실제 STEP가 정상형의 재료 부분집합인지 별도 비파괴 양방향 차집합 검사를 진행 중이다. 전체612쌍 거리 실행도 아직 미완료로 유지하며 그 결과를 합격으로 표시하지 않는다. 두 실제 증거와 기존 나머지 항목을 결합하는 별도 명시적 검증 절차를 준비한다. 수용부 끝부분 정리, 최종 바닥/결합부/native/인쇄 파일 검사는 남아 있고 canonical 파일은 아직 교체하지 않았다.

최종 회귀 수집기에 전체 높이 구간 및 자석 부분집합 시험을 필수로 추가했다. 실패 시험을 먼저 확인한 뒤 수정하여 수집기4개와 Git 바이트 보존2개 시험이 통과했다. 별도 `strata_bundle` 부모 선택과 증거3개/양쪽 형상 이력 보존 경로도 TDD로 추가하여 snapshot9개 시험이 통과했다. 이는 도구 회귀 결과이며 실제 이력 저장·수용부 수정 실행을 완료했다는 의미는 아니다.

후속 도구 통합은 원래 V2 검사기를 완화하지 않고 별도 `right-lower-strata-predicate-bundle-v1` 및 `right-receiver-strata-predicate-transfer-v1` 스키마를 사용한다. 보강 전 전체 증거를 불변 이력에 보존하고, 실제 bounded subtraction 검사에서 모든 추가/계획 밖 제거/보호 구조 손실이 각각 정확히0일 때만 부품 비간섭을 상속한다. source 보고서를 native 직접 검사로 바꾸지 않으며 Fusion 재열기 형상과의 정확한 양방향 재료 동일성은 별도 요구한다. 새 원본 묶음 시험8개, 이력9개, 수정 후 증거 연결7개, 독립 delta12개가 통과했다. 독립 서브에이전트의 읽기 전용 통합 검토도 게시 차단 결함을 발견하지 못했고 기존 정상형48개 바인딩 불일치0을 재확인했다.

오른쪽 하판 게시 항목은 기존 상부 목 검사 대신 두 바닥 수용부의1.20 mm 전체 링·연속 목·높이 전체 수컷 재료·8개 실제 국소 이동 충돌을 확인하는 `floor-capture`를 요구하도록 연결했다. 상판 분할 검사는 변경하지 않았다. 전체 envelope/조립 검사도 오른쪽의 별도 전체 증거를 검증하도록 연결했고 왼쪽은 direct V2를 유지한다. 조립 검사 코드가 바뀌었으므로 이전 `left-stack-review.json`은 현재 코드에 대한 증거가 아니며 실제 재실행이 필요하다. 해시만 갱신하지 않았다. 최종 회귀 필수 목록은 중복 없는62개 모듈이며 전체 중간 실행이 진행 중이다. 아직 최종 보고서 수집/게시/커밋/푸시는 수행하지 않았다.

62개 모듈 중간 회귀 실행은316개 시험을435.960초에 모두 통과했다. 최종 전체 보고서에 source-bound된 실행은 별도로 남아 있다. 최신 source/native 연결 코드로 왼쪽 바닥2종·void·자석 입구의4개 파생 보고서를 실제 입력 재검증 후 재생성했고 모두 통과했다. 왼쪽 조립 간섭 검사도 두 실제 STEP를 다시 가져와 정상/자석 각5개 높이 구간을 검사하여 `pass`, errors=[]로 완료했다.

자석형의 독립 실제 부분집합 검사는 통과했다. A 양방향 재료 차이0, B 추가 재료0/추가 솔리드0/추가 면0, B 제거21.714688421612962 mm³·4솔리드로 예상21.71468842161265 mm³와 일치했다. 보고서 SHA150a3a5c0940a2c7cbbc336b54ac03d8c171728560111b6404fb37a7bfbbfdd8 및46개 바인딩을 확인했다. 이 결과와 실제 정상형11구간/12경계면 증거를 합친 별도 strata predicate bundle을 실제 생성하여 `pass`,55개 현재 바인딩 일치를 확인했다. 원래 V2 `fail`과 양 variant46.794929654225015 mm³는 그대로 보존한다. 이로써 해당 변경 전 형상의 전체153개 부품 보호 영역에 대한 비간섭은 새로운 명시적 방법으로 입증되었으며, 미완료612쌍 진단을 합격으로 변경한 것이 아니다.

실제 `--snapshot-only --parent-proof strata_bundle`도 완료하여76개 소스/증거를 `lower-development/receiver-cleanup-inputs`의 불변 이력으로 보존했다. 이후 오른쪽 normal/magnetic 생성물 변경 시 이 과거 증거를 현재 STEP의 직접 검사로 표시하지 않는다. 수정 후 실제 bounded subtraction·바닥·결합·조립·native·STL 검증은 여전히 필요하다.

### 수용부 수정 STL 실패와 제한적 직렬화 보완

두 수정 생성기의 첫 실제 실행은 B STL의 watertight 검사에서 실패했다. 일반 부피 오차0.0044651997231994756 mm³, 자석형0.010256539171678014 mm³였다. 생산기 delta/floor·간격·STEP roundtrip 가드를 지나 STL 검사까지 도달했으나 수치 지역변수는 보고서로 저장되지 않았으므로 그 값을 합성하지 않는다. STEP/STL은 부분적으로 바뀌고 generation은 원래 기록이어서 일치하지 않으며 사용할 수 없다. 원본76개 snapshot은 그대로이고 부분 출력8개/실행 코드5개는 `lower-development/receiver-cleanup-attempt-1`에 해시 확인 후 보존했다. 소형 실패·코드 기록은 versioned diagnostics에도 보존했다.

독립 읽기 전용 진단에서 두 B STL 모두 두 번째 수용부의 X84.312004089..84.314399719/Y88.846359253..88.847953796/Z−1..2.5에 정확히 면적0인 퇴화 삼각형6개가 발견됐다. 나머지 본체 자체는 단일 닫힌 메시이고6개 부가 facet은 면적/부피0이다. A STL은 정상이다. 이 작은 형상 폭은 약0.0000032 mm로 STL float32 좌표 간격보다 작다. 이는 전체 STEP의 새 실물 결함 판정이 아니라 출력 직렬화의 퇴화 facet 원인분리다.

새 `kc2_stl_zero_area_filter`는 직렬화된 float32 좌표의 면적0 여부를 유리수 외적으로 재확인하여 그런 facet만 제외한다. 양의 면적·좌표·방향·법선·속성 바이트는 바꾸지 않고 hole-fill이나 허용치 welding을 하지 않는다. 남은 facet 레코드/순서·bounds 동일성과 닫힌 양의 단일 본체를 요구한다. root와 독립 에이전트가 실패한 실제 두 B STL을 메모리에서 재검증해 각각6개 제거 후 통과를 확인했다. 부피 합산 차이는1.0913936421275139e−11 mm³로 기록하고, 원래 비퇴화 facet 바이트 동일성이 더 강한 근거임을 구분했다. 원본 실패 파일을 통과로 수정하지 않았다.

필터3개와 producer 연결·불변 snapshot 시험의 RED→GREEN 후 stage에 이 단계를 넣었다. 기존 mesh 검사는 그대로이며 helper/test 소스와 정규화 감사값을 새 generation에 연결한다. 원래 snapshot부터 전체 생산기를 다시 실행 중이고 첫 실행의 지역변수나 부분 출력을 완료 결과로 재사용하지 않는다. core 필수 회귀 목록은64개 모듈이다.

소비자 정적 감사에서 frozen native reviewer의 옛 right-void 경로가 새 STEP와 충돌하는 문제도 발견했다. 기존 upper/left 증거 코드는 유지하고 새 `review_kc2_right_lower_native normal|magnetic`을 추가했다. 전체 source/native STEP의 닫힌2솔리드·소유권과 비파괴 양방향 재료 차이를 검사하며, 새 실행 코드 바인딩을 right native transfer에 강제했다. 새 native 시험3개와 native transfer10개가 통과했다. 아직 실제 right Fusion/native 실행은 하지 않았다. latest helper에 맞춰 왼쪽4개 native 파생 증거를 다시 검증·생성해 통과했다.

### 수정된 생산기의 실제 재실행

`CON-ARCH-006`: 자석형 두 번째 전체 생성은 exit0으로 완료했다. 새로운 generation/출력/소스85개 바인딩을 root가 다시 확인했다. 실제 제거9.877254749547042 mm³, added/off-cutter removal/floor removal/remaining candidate 각각0.0이고 A/B 최소 간격0.40003143179389444 mm다. A의 정규화 제거0개, B는 정확한 면적0 facet6개만 제거했으며 양쪽 STL은 닫힌 단일 양의 체적 메시다. B의 출력 SHA-256은 `cfd81d6c7cc3a06bf45786c33aacb27659d33d40a43620d260d458c5a2666a85`다. 이 기록은 생산기 완료 증거이며 독립 실제 delta/floor-capture/native 및 최종 배포 승인을 대신하지 않는다. 자석형 독립 floor-capture를 시작했고 일반형 생산기 종료를 기다린다.

일반형도 두 번째 전체 생성 exit0이다. 담당 에이전트가81개 source와3개 출력 SHA를 확인했고 generation SHA는 `5cb639f42c8b34f9595177294da569fdf78f631084eb1ad6f49c1426e8d630aa`다. 제거량/각0검사/간격은 위 자석형과 동일하며 A0/B6 정규화와 닫힌 단일 STL 검사가 통과했다. 새 STEP을 읽는 독립 delta 검사를 시작했다.

자석형 별도 `review_kc2_lower_floor right --magnetic`이 exit0/pass/errors[]로 완료됐다. root가88개 source 바인딩을 재확인했다. 두 본체 각각 바닥 Z−2.2..−1.0의1.2 mm 일정 연결 단면, enclosed floor void0, STL 단일/닫힘/양의 부피,150 mm 범위와 BRep 대비 bounds/volume 검사를 통과했다. 이는 실리콘 발/실물 접착 검사가 아니다. 양쪽 floor-capture, right magnetic entry 및 전체 조립 검사는 별도로 진행한다.

배포 계약의 읽기 전용 독립 감사에서10개 job/35 CAD/15 STL/71개 필수 보고서 경로와 안내 링크,76개 snapshot SHA·경로의 비중복 매핑을 확인했다. root의 전체 보고서 현재 바인딩 점검에서는52개가 상태/직접 source SHA와 일치했고, 나머지19개는 예상대로 right native2개가 구모델 연결로 stale, 나머지는 진행 예정인 right floor/capture/void/stack/entry/central/envelope/tests였다. 이 개수는 해당 시점의 메타데이터 검사이며 모든 보고서의 의미 검증을 새로 실행했다는 뜻이 아니다. 새 native 검증과 최종 배포 gate는 아직 남아 있다.

자석형 실제 floor-capture가 exit0/pass/errors[]로 완료됐다. root가87개 source SHA를 확인했다. gap0.40003143179389444 mm/overlap0이며 두 본체의 일정1.2 mm 바닥에 missing/extra 각각0, 두 결합부의1.2 mm 전체 ring 및 full-height male root/head 손실 각각0이다. 각 두 측정 위치의 throat2.8000800000000083 mm/shoulder0.8499599999999958 mm,8개 실제 ±1 mm XY 이동 교집합은 모두 양수(최소0.6958645412733239 mm³)다. 이는 실제 CAD의 기하학적 포획 증거이며 힘/강도 시험은 아니다.

긴 연산의 원인 위치만 읽기 위해 ignored `.codex-tmp/diagnostic-tools`에 py-spy0.4.2를 설치했다. 실행 중인 모델/검사 소스는 수정하지 않았다. 단일 stack sample에서 normal floor-capture는 CAD distance, independent delta는 solid validity, magnetic entry는 Boolean difference 안에 있었다. 이미 끝난 magnetic PID에 대한 첫 sample은 process-open 오류였고 이어 원래 session의 exit0와 실제 보고서를 확인했다. 이 진단 자체는 기하 검증 증거가 아니며 profiler를 최종 제품 의존성으로 추가하지 않는다.

일반형 실제 floor-capture도 exit0/pass/errors[]로 완료했고 보고서 SHA는 `75f3ec1a09c83cbfdea3154d3475bd5b921ac5081f81d36e321ca9d993bfa913`다. 담당 독립 에이전트가87개 바인딩과 publisher 의미 검사를 확인했고 root도 바인딩을 다시 확인했다. 두 본체 바닥 일정 프리즘 missing/extra0, 두 전체1.2 mm ring/root/head 손실0, gap0.40003143179389444 mm/overlap0, throat2.80008 mm와8개 실제 양의 이동 교집합이 확인됐다. 일반형 전체 바닥/STL 검사를 후속 실행한다. 독립 cleanup delta는 normal 단계를 지나 magnetic 계산 중이고 최종 상태는 아직 미정이다.

일반형 별도 전체 floor/STL 검사는 exit0/pass/errors[]다. 보고서 SHA `8c4fdec8bce5aba0eaa24e751a78762e5f0565cfb188f0e880bcabd368cab0d8`,88개 현재 source 바인딩을 에이전트와 root가 확인했다. 두1.2 mm floor는 연결 Polygon/내부 구멍0, 두 STL은 닫힌 단일 양의 메시이며 A88.59375×95.5759964×6.30/B83.0437088×125.8259964×7.20 mm로150 mm 범위 안이다. BRep와 bounds 오차3.601e−6 mm, 부피 오차 약0.00391114/0.00446520 mm³다.

새 right magnetic-entry 실제 검사는 exit0/pass/errors[]이며92개 source SHA를 root가 재확인했다. Y103/111 통로·원래 pocket 차폐0, 뒤벽/주변 재료 손실0이다. actual optional void21.714688421612962 mm³와 expected21.714688421612955 mm³를 비교해 missing/extra/added 각각0을 확인했다. 실제 자석의 흡착력은 이 검사 범위가 아니다. integrated central actual 검사를 시작했고, cleanup 최종 비교 및 right native/전체 envelope/최종 회귀·배포 검사는 아직 남아 있다.

### 중앙 통합 실패와 왼쪽 새 재료 한정 수정 계획

`CON-ARCH-006` integrated central 실제 검사는 네 조합 모두 실패했다. 각 접점의 의도 밖 겹침은 약3.57910588235 mm³로, 실패 원본은 `diagnostics/central-overlap-attempt-1/integrated-review.json`에 SHA `5d5cb315a90dd18caa30ccc721554891ca3fb8567d5b26a8412d1d6ef8015950`로 보존했다. normal 두 접점의 독립 국소 실제/비파괴 교집합 진단은 같은 겹침을 확인했고121개 바인딩이 일치했다. 겹침은 전부 right isolated feature 안이며 left isolated male와 기존 left canonical stock 포함량은0이다. 공통 좌표 X1.2..1.6,Y±1.2..2.55,Z−2.2..1.5이고 left 새 wall/floor_addition 투영 안이다. 자석형 국소 진단을 별도 실행했다고 주장하지 않는다.

기존 SRS의 중앙 자유공간용 새 외벽/새 바닥 국소 제외 허용에 따른 LEFT ONLY 후보: common X=.1−left local X, Y=localY−95 또는−117에서, wall과 box(0,−2.85,2,2.85)의 교집합을 사용한다. Z−1..1.5에서는 exact male XY를 빼고 제거하며 Z1.5..1.8은 해당 wall 전폭을 제거한다. 폭0.5 mm의 얇은 잔여 외벽을 남기지 않기 위한 전폭 창이다. 기존 wall Z1.8..4.1은 폭1.2/높이2.3/길이5.7 mm lintel로 유지하고 지지/브리징을 다시 검증한다. 바닥은 right root_floor의0.30 mm 외곽 여유와 left floor_addition 교집합에서 male XY를 빼고 Z−2.2..−1만 제거한다. 기존 canonical 재료·male·70키 받침·17나사/등록/자석은 제거하지 않는다. 남은 바닥의1.2 mm 일정 두께/연결성을 실제 검사한다. 현재는 독립 계획 검토 및 실패 회귀시험 전 단계이며 형상은 아직 변경하지 않았다. right 완료 증거와 원본 실패 기록을 바꾸지 않는다.

독립 계획 검토에서 두 Y 각각 lowwallcut3.96/transition6.84/floorcut2.31 mm², 실제 unintended 단면 누락0, 기존 stock/male/registrar 절삭0 및 전체 바닥 연결 Polygon/내부 hole0을 확인했다. 원래 안내 혀 부근0.15 mm는 유지되고 male 밖 새 바닥 여유만0.30 mm다. 명시적 치수 보완을 SpecKiwi CLI dry-run 뒤 CON-ARCH-006 statement에 추가했고 기존 statement가 완전히 그대로인 prefix와 추가문장의 roundtrip 일치를 확인했다. Status=in_progress/Stability=evolving을 유지한다. 새 helper `kc2_left_central_relief`의 회귀3개는 missing-module RED 후 GREEN이며 실제 CAD는 아직 변경 전이다. 새 producer/snapshot과 독립 left void 검토기를 별도 TDD로 구현 중이다. 최종 필수 회귀 목록은67개 모듈로 늘렸고 필수 목록 누락 시험의 RED→GREEN 및 Git-byte 검사를 포함한9개 시험이 통과했다. 인쇄 안내 payload에 양쪽5.70 mm bridge와0.15/0.30 구분을 추가했으며 guide gate가 통과했다. 이는 아직 미게시 payload이다.

오른쪽 독립 cleanup delta는 최종 exit0/pass, strict_transfer_eligible=true다. 각 variant 실제 제거9.877254749553105 mm³,9개 required stock/9개 protected role 각각0,added/off-cutter/A변경/floor/pocket/remaining 및 두 paired differences0이다. delta SHA `574b0852c3cfbf286e94c888f0807b9c06663f5c9854d4706fc1eac183229f7f`(87개 바인딩), 새 strata transfer SHA `3a364a09cb6ca8d64c86d570877ce51147ab04523c1b8c3e4711e791a4380923`(90개 바인딩)가 확인됐고 root도 전체 transfer qualifier를 실행해 True를 확인했다. 원래46.7949의 V2 실패는 변경하지 않았다. 실제 right stack도 exit0/pass/errors[]이며136개 바인딩과 세 upper의 각 높이 overlap0/등록 측면0.25 mm를 독립 에이전트가 확인했다. right stack SHA는 `fb81672c87b6655c6c60eaa28b7800561a7cee35a2df8db7bee6b72936686d0b`다. 중앙 LEFT ONLY 수정이 남아 전체 조립/인쇄 승인은 아직 없다.

왼쪽 수정 생산기6개 시험은 누락/stale/충돌 snapshot, archived 필수 closure 삭제, 보호재료 절삭, 비솔리드 조각, 개별 cut 잔여를 실패시키는 TDD 후 통과했다. whole/owned topology는 hash bucket과 isSame multiset으로 비교해 불필요한 O(n²) 탐색을 피한다. 독립 left void 검토기7개 시험은 literal 치수, 이전 generation 거부, 원본 재료 보존, 떠 있는 Face/Edge/Vertex, required stock의 개별 비음수·유한·합계 일치를 검사한다. root가 helper/producer/reviewer/최종회귀수집기/Git-byte의22개 시험을 실제 실행해 모두 통과했다.

`stage_kc2_left_central_relief --snapshot-only`가 exit0으로 완료했고 root가 보존 후 archived 원본들로 필수 closure를 재구성해 `verified_historical_snapshot`,132개 바인딩 일치를 확인했다. 왼쪽 두 원본과 중앙 실패/국소진단의 명시적 alias가 `lower-development/left-central-inputs/snapshot-map.json`에 있다. 그 뒤 일반형과 자석형 전체 생성기를 각각 실행 중이며 아직 terminal 완료/독립 새 형상 통과는 아니다. 관련 소스는 동결했다. 오른쪽 두 F3D는 실제 Fusion 저장·재열기·STEP readback을 완료했고 owned idle Fusion은 문서0 확인 후 종료했다. 오른쪽 independent native material 비교가 별도 실행 중이므로 Fusion 성공만으로 native 동일성을 주장하지 않는다.

왼쪽 첫 생성은 normal session92801/PID37704와 magnetic20531/PID42572 모두 export 전에 exit1로 끝났다. 실제 제거29.44799999999988 mm³, added/off-cutter/remaining-cut 및 기존 canonical baseline 누락 전후는 모두0이나, nominal male 누락 전후가 각각0.9976846887098765 mm³였다. 실패 기록 SHA `e1ff19d56bda5bcd24e3a557a7f8f614ea8220af507825c739a9cba97964861f`와 실행 코드4개는 `diagnostics/left-central-attempt-1`에 보존했다. 당시 아직 실행하지 않은 독립 검토 코드2개도 별도 표기로 보존했으며 전체 진단 인덱스35개 SHA가 일치한다.

독립 진단에서 원래 `place_feature_solids`가 Y95 부착 뿌리를 기존 component clearance와 겹치는 XY0.3990738754840532 mm², Z−1..1.5 구간만 의도적으로 제외함을 확인했다. 그 부피0.997684688710133 mm³가 실패량과 일치하며 Y117 제외량은0이다. 잘리지 않은 nominal XY 전체 프리즘은 올바른 보존 기준이 아니었다. 허용오차를 늘리거나 전후 누락량 같음을 면제하지 않고, 이미 immutable132개 closure에 있던 실제 isolated STEP 두 개를 각각 해시 검증·단일 closed solid 검사한 뒤 각 Y별 `isolated − before`와 `isolated − after`가 정확히0인지 검사하도록 생산기를 수정했다. 절삭용 nominal XY는 보수적인 보호 영역으로 그대로 유지하고 실제 모델 변경 치수는 수정하지 않았다. 새 loader/개별 보호 검사의 RED(2 errors)→GREEN과 기존 회귀를 포함한10개 시험이 통과했다. 실제 두 기준 STEP를 재읽어 Y95 32.15431531129067/Y117 33.15200000000008 mm³를 확인한 뒤 두 생성기를 다시 시작했다. 이 재실행은 아직 독립 형상 합격이나 게시 완료가 아니다.

독립 left void 검토기도 자체 실제 isolated STEP loader 및 각 Y의 exact0 보호 검사를 RED→GREEN으로 수정했다. 두 reference와 manifest의 원본 source/output SHA, 단일 closed/owned solid 및 기록된 부피를 확인하며 작은 양수/음수/NaN/bool/누락도 보호량 합격으로 처리하지 않는다. root가 생산기·검토기·계획·최종회귀수집·Git-byte의25개 시험을 실행해 통과했다. 바닥/벽 치수와 기존 소켓 회피는 변경하지 않았다.

오른쪽 normal native 독립 비교 SHA `2458d4d71027759d685c9a169cf7d5ebd6d6fcdeacdf2a7a9aae2e39ec7a10c8`, magnetic SHA `4e54d59fd1d07894e0039d6f952566a8631a3c61d8b023868e5f459b925b3e39`가 각각 exit0/pass이며 각각105개 바인딩 일치를 확인했다. 두 variant A/B에서 실제 비파괴 차집합 missing/extra 각각0, valid empty/solid0/face0이다. 이어 right floor2/floor-capture2/void/magnetic-entry 총6개 native feature transfer를 실제 생성·전체 qualifier 검증하여 통과했다. 이들은 exact native 동일성을 통한 기존 실제 source 검사 결과의 전이이지 기능 CAD 검사를 다시 실행했다는 주장이 아니다. 전체 report inventory71개 중 당시68개 status/source current, central 실패1, envelope/test-execution 누락2다. 여기에는 아직 새 left 생성이 덮어쓰지 않은 구형 left 보고서가 포함되므로68을 최종 합격 수로 해석하지 않는다. 주문한 PCB/Gerber16개는 root가 기준 커밋 Git blob과 다시 바이트 대조하여 모두 일치함을 확인했다.

왼쪽 attempt2 normal8335/magnetic35883 모두 exit0으로 완료했다. generation SHA는 각각 `c85891226a2d66c315407e58327e26b882a1f44e8b8e241eb582657f12e56999`, `f48a48e67efdc96c56d268a94af8874735d0df59ae0d35972f07e494285358cf`이며139개 source와 각 STEP/STL output SHA가 일치한다. 실제 제거29.44799999999988 mm³이고 added/off-cutter/remaining-cut/full baseline loss 및 각 Y95/117 actual male의 before/after loss는 모두 정확히0이다. 두 새 STL은 닫힌 단일 양의 메시이며 STEP roundtrip을 통과했다. 뒤이은 독립 floor normal18228/magnetic50173도 pass,143개 source 일치다. 실제1.2 mm 바닥 단면은 단일 Polygon/내부 hole0, 면적13954.646947066527 mm²다. 두 STL extents139.312503×125.825996×7.20 mm, bounds오차3.601e−6 mm, 부피오차 normal0.00253236/magnetic0.00826904 mm³다. Magnetic floor SHA `2972176e1d90794fb05d95601da14d85524e90fa83874a662f251a5531259e03`.

새 실제 integrated central 검사21587은 exit0/pass로 완료했고145개 source SHA를 독립 에이전트와 root가 확인했다. 보고서 SHA `7509cfcbfe29add54de58267225fe2524b85e78e1981c37661517ed4dcddb6ce`. normal/magnetic×Y95/Y117 네 행 모두 required-left/right-missing, free/overhead obstruction, unintended-overlap, missing-contact, rigid-insertion-obstruction은 각각0이다. 명목 의도 접촉0.003334117647058707 mm³와 실제 약0.00333411764706456 mm³가 일치한다. 원래 실패는 앞서 보존된 역사적 기록으로 유지한다. 이는 cropped 중앙 실제 BRep/7.8 mm nominal tongue sweep 검증이며 전체 키보드 envelope sweep과 출력물 힘·강도는 아직 별도다. 왼쪽 새 전체 void/자석 entry, stack, Fusion/native와 최종 전체 envelope/tests/publication은 계속 진행 중이다.

왼쪽 새 magnetic-entry76794는 exit0/pass,147개 source 일치, SHA `989b24e2885d0bfb1358d0b3b715db00e3ab9685f4a3306a862d6db1aaee4fb3`. Y103/111 external corridor/pocket 차폐와 backweb/original surround 손실은 각각0이며 actual optional void21.71468842161266 mm³의 missing/extra/magnetic-added도0이다. 이어 새로운 독립 전체 left void97295도 exit0/pass,147개 source 일치, SHA `ba9b4bb03d8bfcfc7f1b89421ee67966fd8e779f9711d22e3939b993afea96ff`. 양 variant 여섯 기본 metric,10개 required-stock 각각,두 protected actual male 각각,자석 missing/extra/blocked/entry는 모두 정확히0이다. 허용된 기존 stock 삭제는 없다.

왼쪽 두 F3D를 실제 Fusion2705.1.11에서 다시 저장·재개방하여 새 STEP readback을 얻었다. Normal native-generation SHA `6a63ec2fad18aec8ed85c9b00b6053f6a1742d7557619c2dfc380e3b5ceb3cf1`, magnetic `9e82af47d8995ac2daedc659f3d1770e3a5bca24f276e597aa7854a7f5f0d137`이며 소스/output 해시를 확인했다. 실행한 Fusion은 문서0 확인 후 정상 종료했다. 이후 두 별도 독립 native material 비교를 실행 중이며 저장 성공을 그 비교의 합격으로 대신하지 않는다.

왼쪽 실제 stack3980도 exit0/pass,170개 source 일치, SHA `5f4a5c1734ea47f9ec42b6a5e3dfad63b81b230d852d69a5c65ae6a07253a422`. 양 variant의 PCB 위 실제 단면과 세 상판 비교가 통과했고 등록 높이 구조가 일치한다. 동시에 실행한 중간 mandatory67모듈 회귀93109는344 tests/354.743초/exit0/OK다. 이는 아직 누락된 최종 native/envelope 보고서에 source-bound된 최종 test-execution이 아니며, 배포 전 최종 수집을 별도로 실행한다.

왼쪽 independent native normal80478/magnetic34696은 모두 exit0/pass,각158개 source 일치 및 sole-body missing/extra 각각 정확히0으로 완료했다. 각각 SHA `d645f1194246fabc8374ba4165b20dcfaf891ea93512af62d03b620e8a850b14`, `31f11f0ae227a276975fdd4cbf91ef48f1cae40680ae9c78c8313a7a3e48c6f3`. 네 left native feature transfer도 실제 생성·전체 qualifier 검증을 통과했다. 첫 전체 실제 envelope26098은10 jobs/15 STL,272 source bindings,errors[]/exit0/pass이며 SHA `ecc67b1a0d491fcecb8622acd0cd5d605cfc53aedf0885ab3e43153811def432`다.

### 최종 SRS 일관성 및 STEP 게시 형식

독립 SRS 검토에서 승인된 최신 Requirement 문장과 충돌하던 구형 AC-2/5/6/9/10/11(외벽 금지,외부 개방 바닥,전고2.50 mm/.20 mm 결합,옛 나사/경로)을 확인했다. SpecKiwi CLI의2000 UTF-16 길이 제한 때문에 기존 조건을 짧게 표현하되70키/17MH/부품 여유/지지/150 mm/실제 Fusion/실물 기준을 유지하여 여섯 AC를 정리했다. 모든 dry-run 후 적용하고 정확한 text roundtrip,기존 Requirement 본문/status=in_progress/stability=evolving 유지,11개 AC 모두 unchecked를 확인했다. 물리 검증이나 새 발주 승인을 하지 않았다. AC9는 게시할 편집용 STEP와 원본 native-readback 증거를 구분한다.

실제20개 source/native STEP byte 검사에서 줄 끝 공백이 발견됐다. Source10개는 각각36,385~122,885행의 외부 ASCII space였고 native10개는 exporter 주석 내부의1개였다. native 주석은 임의로 바꾸지 않는다. 신규 `kc2_step_whitespace`는 보호된 문자열/바이너리/주석·줄바꿈을 보존하며 외부 ASCII trailing space/tab만 삭제하고 독립 구문 재검사 및 삭제 바이트 복원으로 동일성을 증명한다. 보호 구문 내 trailing whitespace나 잘못된 framing은 거부한다.4개 RED→GREEN 시험과 실제 source10개 read-only 변환 검사가 통과했으며 아직 원본 CAD 파일은 변경하지 않았다.

게시기는 편집용10 STEP만 정규화하고 검증 원본은 `evidence/raw-step/*.step.raw`에 보존하도록 수정했다. 기존 generation/actual/native source SHA는 변경하지 않고 portable resolver가 원본을 읽는다. Manifest는 정확한10개 mapping/code/raw/normalized SHA와 제거 수/lexical equivalence/whitespace=false를 기록하고, verify는 원본에서 재계산해 게시본과 정확한 바이트 비교를 수행한다. 숫자 변경 후 output SHA만 갱신,누락/잘못된 mapping,원본 변경,boolean/count 혼용과 transaction rollback을 시험했다. 관련40개 회귀가 통과했고 독립 검토14개 시험도 통과했다. 최종 mandatory 목록은69개이며 현재 source-selected70개 모듈이다. Git-byte 시험의 RED→GREEN으로 신규 helper/test -text를 보장한다.

이 publisher 소스 개정 전의16개 코드/통과 보고서를 `diagnostics/pre-step-normalization-validation`에 `PASSED_BEFORE_PUBLISHER_FORMAT_REVISION`으로 보존했다. 전체 진단51개 SHA가 일치한다. 기존 PASS를 실패로 바꾸거나 새 실행 결과로 가장하지 않는다. 최종 publisher/helper/tests를 동결한 뒤 양측 stack,10개 native feature transfer,전체 envelope를 다시 실행 중이다. 아직 최종 test-execution/preflight/publication/isolated portable 검증 및 commit/push는 완료하지 않았다.
