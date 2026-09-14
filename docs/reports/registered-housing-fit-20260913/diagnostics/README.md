# 보존된 진단·개정 전 검증

CON-ARCH-006의 역사적 원인분리 및 개정 전 검증 기록이다. 현재 배포의 PASS 입력이나 주문 승인 증거가 아니다. [index.json](index.json)에 51개 파일의 원래 논리 경로, 보존 경로, SHA-256 및 분류를 기록했다. 복사 전후 바이트가 같으며 원본 JSON의 값과 상태는 수정하지 않았다. Git 커밋·푸시는 상위 작업에서 별도로 수행한다.

| 기록 | 원래 상태와 의미 |
|---|---|
| [거리 시도 1](component-distance-attempt-1/interrupted.json) | `interrupted_not_accepted`: 첫 실행 중단, 전체612 미완료 |
| [거리 시도 2](component-distance-attempt-2/interrupted.json) | `interrupted_not_accepted`: normal B/tool100까지 관찰 후 승인된 종료, 전체612 미완료 |
| [개별 다이오드](d8/right-diode-failure-diagnosis.json) | `diagnosed_not_accepted`: 개별39곳 검사와 aggregate 결과 차이의 원인분리 |
| [정확한 aggregate 다이오드](d8/right-exact-aggregate-diode-diagnosis.json) | `diagnosed_not_accepted`: 실제32도구×2솔리드 중 D8에서 전체 도구 체적 반환 |
| [비파괴 D8](d8/right-d8-nondestructive-diagnosis.json) | `diagnosed_not_accepted`: 새 입력에서 연산 전후 거리와 비파괴 Common 비교 |
| [D8 경계·단면](d8/right-d8-boundary-diagnosis.json) | `diagnosed_not_accepted`: 점 분류 불연속과 실제 경계 거리·국소 단면 비교 |
| [D8 shell·외부 seed](d8/right-d8-shell-seed-diagnosis.json) | `diagnosed_not_accepted`: 닫힌 경계 간 거리와 국소 vertical-prism/외부 seed 증거 |
| [Receiver STL 시도 1](receiver-stl-attempt-1/failure.json) | `failed_not_accepted`: normal/magnetic 양쪽 part B의 watertight 검사 실패, generation 갱신 전 중단 |
| [중앙 실제 조립 실패](central-overlap-attempt-1/integrated-review.json) | 원래 `failed` 상태 보존: normal/magnetic의 두 접점 모두 의도하지 않은 실제 겹침 |
| [중앙 겹침 국소 진단](central-overlap-attempt-1/overlap-localization.json) | `diagnosed_not_accepted`: normal 두 접점만 실제 단면·isolated feature·이전 stock과 비교 |
| [왼쪽 보호 기준 시도 1](left-central-attempt-1/failure.json) | `failed_not_accepted`: normal/magnetic 모두 nominal male 보호 기준 검사에서 출력 전 중단 |
| [발행기 형식 개정 전 전체 외형 검사](pre-step-normalization-validation/actual-envelope-review.json) | `PASSED_BEFORE_PUBLISHER_FORMAT_REVISION`: 당시 실제 검사는 PASS, 새 발행기 소스에 대한 최종 증거는 아님 |

`pre-step-normalization-validation/`에는 발행기1개와 테스트2개, 전체 외형 검사1개, 좌우 조립 검사2개, native feature transfer10개를 보존했다. 복사 시 289개 고유 소스 연결을 확인했다. 이는 실패가 아니라 STEP 발행 형식 처리 개정 **이전**의 통과 기록이다. 원본 JSON의 `pass`와 수치를 유지하고, 개정 뒤 실행되는 새 조립·transfer·외형 보고서와 구분한다. 이 그룹은 CAD 형상을 수정하거나 STEP/STL/F3D를 복사하지 않는다. 전역 index의 `archive`는 무시된 보존 위치이고 `destination`은 Git으로 보존할 작은 사본이다.

왼쪽 보호 기준 시도1은 두 실행 모두 절삭량29.44799999999988 mm³, 추가·범위 밖 절삭·절삭 잔여·기존 canonical 하판 손실0을 보고했다. 그러나 nominal male 기준의 누락량이 절삭 전후 모두0.9976846887098765 mm³여서 실패했다. 전후 값이 같다는 사실만으로 보호 검사를 승인하지 않는다. STEP/STL 및 generation JSON 출력 전에 중단되었고, 당시 producer/helper 및 각 테스트4개를 그대로 보존했다. 별도 `pre-correction-unexecuted/`의 독립 reviewer와 테스트2개는 수정 전 소스이며 실제 하우징에 실행된 검사로 간주하지 않는다. 원본132개 입력 연결은 `.codex-tmp/registered-housing-fit/lower-development/left-central-inputs/snapshot-map.json`에서 해결한다. 이 실패 기록은 기준 진단이나 이후 재실행의 완료를 의미하지 않는다.

중앙 국소 진단은 두 접점마다 약3.57910588235 mm³의 불필요한 겹침이 새 왼쪽 외벽/바닥과 오른쪽 결합부 사이에 있음을 확인했다. Common과 비파괴 Common이 같고, 해당 겹침은 원래 왼쪽 하우징 및 nominal male에는 없다. 실제 단면의 common X1.2..1.6, Z−2.2..1.5 위치와 단계별 WKT를 보존했다. 실행한 `diagnose_kc2_central_overlap.py`도 바인딩 해시와 같은 바이트다. 수정 계획이나 이후 재생성 완료는 이 실패·진단의 의미에 포함하지 않는다.

Receiver STL 실패와 당시 코드5개도 보존했다. 두 실행은 STEP/부분 STL을 썼지만 generation JSON을 완료하지 못했으므로 해당 혼합 출력은 사용할 수 없다. 실패 보고서에 없는 producer 내부 수치는 추정해 채우지 않았다. 후속 원인분리에서는 각 part B의 정확히 0면적 facet6개를 제거하는 방법이 검토되었다. 선택된 수정은 binary STL의 비퇴화 facet 레코드·순서·좌표·방향·속성 바이트와 bounds를 유지하고 정확히 0면적인 facet만 제거한다. tolerance welding이나 hole filling이 아니다. 전체 재생성과 새 실제 증거가 완료되기 전 이 실패를 해결된 최종 generation으로 간주하지 않는다.

각 거리 시도에는 그때 실행한 checker/helper/test 세 파일을 보존했다. 시도2의 BelowNormal 우선순위 변경 기록도 포함한다. 다섯 D8 checker는 각 원본 진단의 `source_sha256`에 있는 실행 코드 해시와 일치함을 확인하고 복사했다. 이 Python 파일은 역사적 실행 코드이며 이 폴더에서 직접 실행할 도구가 아니다. 의존 파일은 원본 보고서의 소스 연결을 따라야 한다.

STEP/STL/F3D 및 중복 generation/V2 JSON은 복사하지 않았다. 두 시도의 원본 metadata는 기존 논리 폴더 기준 상대 파일명도 포함하므로, 이 축소 보존 폴더에 같은 이름의 모든 입력이 있다고 가정하면 안 된다. 시도2의 세 생략 입력은 receiver snapshot의 `right-normal/generation.json`, `right-magnetic/generation.json`, `right-void-review.json`으로 같은 해시를 찾아 해결한다.

전체 원래 입력의 경로 대응은 `.codex-tmp/registered-housing-fit/lower-development/receiver-cleanup-inputs/snapshot-map.json`과 그 76개 보존 연결을 사용한다. 최종 배포에서는 manifest가 지정한 `evidence/lower-development/receiver-cleanup-inputs/` 위치를 확인한다. 해당 배포가 아직 없으면 이 문서의 경로 설명만으로 portable 재현 완료를 주장하지 않는다. 원래 V2의 실패값은 유지되고, 선택된 전체 component 승인 방법은 별도의 normal Z-strata + 실제 magnetic subset 증거다. 중단 시도들을 합쳐 가상의 완료612 결과를 만들지 않는다.

복사본 검증 예시(저장소 루트, 읽기 전용):

```powershell
$diagnosticIndex = Get-Content -Raw -Encoding UTF8 docs/reports/registered-housing-fit-20260913/diagnostics/index.json | ConvertFrom-Json
foreach ($entry in $diagnosticIndex.files) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $entry.destination).Hash.ToLower() -ne $entry.sha256) {
        throw "Changed diagnostic: $($entry.destination)"
    }
}
```
