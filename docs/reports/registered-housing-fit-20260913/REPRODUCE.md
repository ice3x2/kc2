# Registered housing 재검증·재생성 절차

범위: CON-ARCH-006, CON-ARCH-007, OPS-ARCH-006. 이 문서는 실행 순서를 설명하며, 아래 전체 재생성을 새 worktree에서 실행했다는 증거가 아니다. 실제 완료 여부는 현재 manifest와 개별 source-bound 보고서로 판단한다. PCB/Gerber 재생성이나 주문 승인 절차가 아니다.

## 1. 기존 배포의 바이트·증거 검증

배포된 commit의 루트에서 실행한다. manifest가 없거나 검증이 실패하면 배포 완료로 간주하지 않는다.

```powershell
python -B -m tools.publish_kc2_registered_housings --verify hardware/MODELS/kc2_registered_housing_manifest.json
```

Python 3.12와 `requirements-cad.txt`의 Shapely가 필요하다. 기준 CAD를 Git blob으로 읽으므로 기준 commit `5b99bcb4567ea1c6bb4f17e54887d4de7614cd03`을 포함하는 Git 이력도 필요하다. 이 검증은 STEP Boolean/Fusion 작업을 다시 실행하지 않는다.

## 2. 재생성은 반드시 격리 worktree에서

현재 생성기·실제 CAD 검토기는 `hardware/MODELS`의 파일을 **개정 전 기준 CAD**로 직접 읽는다. 따라서 배포 후 메인 작업 폴더에서 생성기를 실행하면 안 된다. release 코드와 기준 CAD를 분리한 아래 환경을 사용한다. 새 경로가 이미 있으면 중단하고 다른 빈 경로를 선택한다.

```powershell
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath C:\Work\git\kc2-reproduce) { throw 'Choose a new empty worktree path' }
$releaseCommit = git rev-parse HEAD
git worktree add --detach C:\Work\git\kc2-reproduce $releaseCommit
if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed' }
Set-Location C:\Work\git\kc2-reproduce
if ((Get-Location).Path -ne 'C:\Work\git\kc2-reproduce') { throw 'Not in the isolated worktree' }
$baselineCad = @(python -B -c "from tools.kc2_registered_release_gate import inventory; print('\n'.join(inventory()))")
if ($LASTEXITCODE -ne 0 -or $baselineCad.Count -ne 35) { throw 'Expected exactly 35 baseline CAD paths' }
if ($baselineCad | Where-Object { -not $_.StartsWith('hardware/MODELS/') }) { throw 'Unexpected restoration target' }
git restore --source=5b99bcb4567ea1c6bb4f17e54887d4de7614cd03 --worktree -- $baselineCad
if ($LASTEXITCODE -ne 0) { throw 'Baseline restoration failed' }
python -B -c "from pathlib import Path; from tools.publish_kc2_registered_housings import check_baseline_bytes; check_baseline_bytes(Path.cwd()); print('35 baseline CAD and 16 PCB/Gerber identities match')"
```

`HEAD`는 반드시 재현하려는 **완성된 release 코드 commit**이어야 한다. 위 절차는 새 worktree의 정확한 35개 CAD만 되돌린다. 메인 작업 폴더에서는 실행하지 않는다. PCB/Gerber 16개는 변경하지 않는다. 이후의 생성물도 격리 worktree의 `.codex-tmp`에만 생성한다.

재생성 환경은 Windows Python 3.12, `requirements-cad.txt`의 CadQuery 2.8.0/Shapely 2.1.2 및 mesh 검토에 사용하는 trimesh를 필요로 한다. `load_plans()`는 `C:/Program Files/KiCad/10.0/bin/python.exe`를 직접 사용하여 PCB를 읽는다. 이 경로와 pcbnew 실행 환경이 필요하며 PCB는 읽기 전용이다. Fusion 작업에는 Fusion 내부 Python/adsk API가 필요하다. 실행 환경/Fusion 버전은 새 증거에 기록한다. 의존성 설치나 경로 변경은 이 문서를 작성하며 실행하지 않았다.

## 3. 보존 입력과 perimeter recipe

배포 manifest의 `bindings`가 논리 경로, 실제 `destination`, SHA-256의 기준이다. 다음 자료는 **증거·입력**이며 별도의 활성 CAD 제품이 아니다.

| 논리 입력 | 배포 보존 위치 |
|---|---|
| `.codex-tmp/perimeter-wall-plans.json` | `docs/reports/registered-housing-fit-20260913/evidence/perimeter-wall-plans.json` |
| `.codex-tmp/registered-housing-fit/lower-development/...` | `docs/reports/registered-housing-fit-20260913/evidence/lower-development/...` |
| staged generation/registrar snapshot/review JSON | manifest가 지정한 `evidence/...` |
| 이전 canonical 35개 CAD | 위 기준 Git commit의 동일 경로 blob |
| 최종 staged STEP/STL/F3D | 배포된 `hardware/MODELS`의 단일 canonical 사본; 재생성 입력으로 일괄 복사하지 않음 |

새 worktree에서 perimeter JSON을 원래 논리 경로로 복사하고 manifest의 SHA-256과 비교한다. `.codex-tmp/registered-housing-fit`는 새로 시작한다. 캐시 기반 재실행을 선택할 때만 필요한 `lower-development` 파일을 manifest에 명시된 정확한 논리 경로로 복사하고 각각 hash를 확인한다. 과거 development JSON 내부의 과거 소스 hash는 provenance이며 현재 코드 통과 증거로 다시 해석하지 않는다.

`tools/kc2_perimeter_wall.py`에는 CLI가 없다. JSON의 최초 작성은 inline 작업이었다. 독립적으로 geometry recipe를 재현하는 실행 가능한 예는 다음 테스트에 있다.

```powershell
python -B -m unittest tools.test_kc2_perimeter_wall.PerimeterWallTests.test_CON_ARCH_006_actual_joined_perimeter_existing_enclosures
```

Recipe는 `generate_kc2_magnetic_housings.load_plans()`의 각 side에 대해 `perimeter_plan()`에 다음을 전달한다: `board`, `all_component_cutouts`를 `lower_protected`로, 과거 `solid-filled-plates-20260913/<side>-mx.json`의 `plan_wkt.body/service`, 과거 `reinforced-covers-20260913/<side>-lower.json`의 `new_outline_wkt`를 floor로, `APPROVED_WORLD_OMISSIONS`, `raw_bounds`, `side`. 반환값의 wall/floor_addition/central_removed/service_removed/inner를 해당 `*_wkt` 필드로 보존한다. 높이 bands는 `[-1,2.5]`, `[2.5,4.1]`, floor는 `[-2.2,-1]`이다. 합쳐진 투영 간격/겹침은 `to_world()`로 계산한다. 이 테스트는 recipe의 기하를 검사하며 JSON을 쓰거나 현재 CAD를 통과시키지 않는다. 기존 exact JSON을 재사용하는 편이 출처 추적에 가장 명확하다.

## 4. 실제 생성 순서

각 명령을 **하나씩** 실행하고 성공·보고서 완료 후 다음으로 진행한다. 이것은 자동 batch 스크립트가 아니라 순서가 있는 수동 recipe다. 섹션 5의 CLI 예시는 명시된 모든 조합으로 확장해야 한다. 외부 staged 선행 입력을 먼저 만든다.

```powershell
python -B -m tools.stage_kc2_central_features
python -B -m tools.collect_kc2_profile_splits
python -B -m tools.kc2_joined_sweep
```

첫 명령은 `central/central-features.json`과 좌우 Y95/117 feature-only STEP을 만든다. Lower 생성기의 `place_feature_solids()` 자체는 이 파일을 읽지 않고 같은 함수를 호출해 형상을 만들지만, **integrated central 검토**는 이 JSON/STEP을 직접 읽으므로 생략할 수 없다. 두 번째 명령은 `ab/profiles/{mx,choc_v1,deep_sea}-split-plan.json`을 만들어 right actual profile 검토의 선행 입력을 충족한다. 세 번째 source-plan sweep은 perimeter JSON과 central feature JSON을 읽는다. 이 셋의 완료는 최종 전체 CAD/native 통과를 의미하지 않는다.

그 뒤 side=`left/right`, kind=`mx/choc_v1/deep_sea`의 여섯 조합에 대해 upper를 생성한다.

```powershell
python -B -m tools.stage_kc2_registered_upper left deep_sea
```

동일 명령의 side/kind를 바꾸어 여섯 upper를 생성한다. 특히 left Deep Sea의 `generation.json`에 있는 registrar가 left lower의 선행 입력이다. 그 후:

```powershell
python -B -m tools.stage_kc2_registered_lower left
python -B -m tools.stage_kc2_lower_top_clearance
python -B -m tools.stage_kc2_registered_lower left --magnetic
python -B -m tools.stage_kc2_lower_top_clearance --magnetic
python -B -m tools.stage_kc2_magnetic_access
python -B -m tools.stage_kc2_registered_right_lower
python -B -m tools.stage_kc2_right_magnetic_from_normal
```

Left 최초 생성기는 ordinary wall을 Z4.35까지 만들고 top-clearance 단계가 Z4.10으로 정리한다. `lower_top_clearance`는 최초 STEP/JSON/registrar를 `lower-development/left-<variant>`에, `magnetic_access`는 수정 전 magnetic STEP/JSON을 `lower-development/left-magnetic-before-access`에 **없을 때만** 저장한다. 오래된 캐시가 있으면 새 입력 대신 그것을 재사용하므로 신선한 재생성과 보존 캐시 재실행을 섞지 않는다. 캐시가 의도와 다르면 삭제로 밀어붙이지 말고 새로운 격리 worktree에서 시작한다.

Right magnetic은 완성된 right normal 및 기준 normal/magnetic CAD를 읽는 bounded 변형이다. 이전 rejected `stage_kc2_ab_relief` upper 진단은 이 생성 경로가 아니다.

### Right receiver: 개정 전 증거 → 보존 snapshot → 제한된 정리

위 right 두 생성물은 **receiver 정리 전 입력**이다. 다음 단계까지 완료하기 전 최종 하판으로 간주하지 않는다. 선택된 component 증명은 normal 전체 실제 Z 구간 검사와 magnetic이 그 normal의 실제 부분집합이라는 검사다. 원래 `right-void-review.json`의 component Boolean 실패는 그대로 보존하며, 그 수치를 0으로 고치지 않는다. 과거 612-pair 거리 검사의 attempt 1/2는 중단·미승인 기록이며, 이 새 경로의 필수 검사나 완료 증거가 아니다. D8 국소 진단만으로 전체 component 증명을 대체하는 경로도 아니다.

완전한 fresh 재생성은 아래 **정리 전** 입력을 새로 만들어야 한다. 먼저 다음 두 기존 검토를 각각 실행해 실제 보고서를 보존한다. 현재 이력에서는 둘 다 실패했으므로 자동 성공 batch로 묶지 않는다.

```powershell
python -B -m tools.review_kc2_lower_voids_v2 right
python -B -m tools.review_kc2_lower_split
```

선택된 strata bundle은 원래 V2가 양 variant의 component 항목만 실패하고 나머지 다섯 항목 및 magnet 항목이 정확히 0인 경우만 받는다. 실패 종류가 달라지거나 새 실행이 다른 결과를 내면 원래 기록을 복사·수정해 맞추지 말고 증거 경로부터 재검토한다. 기존 split 실패는 다음 국소 정리의 출처이며 최종 floor-capture 통과로 재해석하지 않는다.

Candidate 작성기는 저장소 `tools` 모듈이 아니라 보존 입력 `.codex-tmp/receiver_cleanup_candidate.py`다. release manifest의 logical path와 SHA를 따라 `lower-development/receiver-cleanup-inputs/provenance/receiver_cleanup_candidate.py`에 보존된 동일 바이트를 **그 원래 논리 경로**로 복원한다. 그 위치에서 `parents[1]`로 저장소 루트를 계산하므로 보존 폴더 안에서 바로 실행하면 안 된다. 보존 script가 없으면 아래 fresh recipe는 완전하지 않다. 새로 임의 작성하거나 JSON hash만 갱신하지 않는다.

```powershell
python -B -m tools.diagnose_kc2_lower_throat
python -B .codex-tmp/receiver_cleanup_candidate.py
python -B -m tools.plan_kc2_lower_receiver_supports
python -B -m tools.plan_kc2_receiver_cleanup
python -B -m tools.diagnose_kc2_receiver_floor_prism
```

순서대로 `right-normal/throat-diagnosis.json`, `receiver-cleanup-candidate.json`, `receiver-supports-plan.json`, `receiver-cleanup-plan.json`, `receiver-floor-prism-diagnosis.json`을 만든다. Candidate는 실제 Z0 단면에서 두 receiver의 R0.60 mouth 끝부분을 선택한다. Support plan은 PCB에서 추출한 받침/레일/나사/리셋, 기존 가림벽, perimeter/registrar의 보호 영역을 읽는다. Cutter plan은 고정된 바깥 여유0.002 mm와 보호 역할 전체를 검사한다. 마지막 실제 STEP 진단은 바닥 Z−2.2..−1의 1.20 mm 주변 stock 및 위쪽 Z−1..2.5의 구간 일관성을 확인한다. 이들은 cleanup의 입력·국소 증거이지 최종 형상 승인 자체가 아니다. 폐기된 blanket-ring repair/mouth 제안은 실행 선행 단계가 아니다.

정리 전 양 variant의 STEP/generation과 원래 V2가 동일 source closure를 유지하는 동안 다음을 실행한다.

```powershell
python -B -m tools.review_kc2_lower_strata
python -B -m tools.review_kc2_magnetic_subset
python -B -m tools.kc2_lower_strata_bundle
python -B -m tools.stage_kc2_receiver_cleanup --snapshot-only --parent-proof strata_bundle
```

앞의 세 명령은 각각 `lower/right-normal-strata-review.json`, `right-magnetic-subset-review.json`, `right-strata-predicate-bundle.json`을 만든다. 전체 normal의 11개 Z 구간·12개 경계와 153개 required 영역, 실제 magnetic의 added=0 부분집합 증명을 함께 검사한다. Bundle의 `computed_common_volume_mm3`는 **null**이며 Boolean 체적0을 주장하지 않는다. 모든 입력 hash 및 의미 검증을 통과한 뒤에만 snapshot을 만든다.

`--snapshot-only`는 두 variant의 원래 STEP/generation, 실패 V2/split, candidate/plan/진단, strata/subset/bundle 및 전체 소스 연결을 `lower-development/receiver-cleanup-inputs`에 보존하고 `snapshot-map.json`에 명시적 경로 대응과 원래 hash를 기록한다. 한쪽을 먼저 바꾼 뒤 다른 쪽을 보존하면 안 된다. 이전 source를 읽는 검사가 남아 있으면 먼저 종료·결과 보존을 완료한다. 기존 snapshot과 충돌하면 덮어쓰지 말고 새 격리 worktree를 사용한다.

```powershell
python -B -m tools.stage_kc2_receiver_cleanup --parent-proof strata_bundle
python -B -m tools.stage_kc2_receiver_cleanup --magnetic --parent-proof strata_bundle
python -B -m tools.review_kc2_receiver_cleanup
python -B -m tools.kc2_receiver_bundle_transfer --parent-proof strata_bundle
```

두 modifier는 같은 immutable 원본에서 각각 새 STEP/STL/generation을 만든다. 기본 `--parent-proof`는 `direct_v2`이므로 위 selector를 생략하지 않는다. 독립 검토는 새 STEP을 다시 읽어 added/off-cutter removal/A 변경/필수 stock·floor·보호 역할 손실, 두 variant의 제거 집합 차이를 검사한다. **엄격한 전달에 필요한 값이 각각 정확히 0**이어야 `right-receiver-strata-transfer.json`을 발행할 수 있다. 작은 비영값을 반올림하거나 producer assertion으로 대체하지 않는다. 새 transfer는 보존된 component 증명과 독립 실제 subtraction 증거를 연결하며 원래 실패 V2는 계속 역사적 실패로 남는다.

첫 modifier 실행은 양 variant의 part B STL watertight 검사에서 실패했다([보존 기록](diagnostics/receiver-stl-attempt-1/failure.json)). STEP/일부 STL이 있어도 generation JSON의 완료 상태·출력 hash가 일치하지 않는 부분 생성물은 사용할 수 없다. 후속 stage는 STL export 직후 `kc2_stl_zero_area_filter.normalize()`를 호출하고 helper/test를 source-bound 입력으로 기록한다. 이 필터는 직렬화된 binary32 좌표의 정확한 유리수 cross-product로 확인한 **0면적 facet만** 제거한다. 남는 facet50바이트 레코드와 순서·bounds는 그대로 유지하며, 양의 면적을 tolerance로 버리거나 정점 welding/구멍 채우기를 하지 않는다. 결과는 닫힌 단일 양의 체적 mesh를 만족해야 하고 새 `parts[].stl_exact_zero_area_normalization` 기록과 STEP 대비 mesh 검사를 거친다. 이 설명은 수정된 생성기의 동작이며 새 전체 재생성·독립 검증이 완료됐다는 선언은 아니다. 실패한 부분 STL을 수작업으로 덮어써 완료 상태로 만들지 않는다.

### Left central: 통합 간섭의 새 왼쪽 재료 한정 정리

오른쪽 receiver 정리까지 끝난 뒤, 아직 정리하지 않은 왼쪽 두 모델의 중앙 통합 실패와 국소 진단을 보존한다. 현재 이력의 원인은 기존 왼쪽 하우징/안내 혀가 아닌 새 wall/floor_addition이다. 다른 실패가 나오면 기존 실패 JSON을 복사하거나 pass로 변경하지 않는다.

```powershell
python -B -m tools.review_kc2_integrated_central
python -B -m tools.diagnose_kc2_central_overlap
python -B -m tools.stage_kc2_left_central_relief --snapshot-only
python -B -m tools.stage_kc2_left_central_relief
python -B -m tools.stage_kc2_left_central_relief --magnetic
python -B -m tools.review_kc2_left_central_voids
```

이는 성공 batch가 아니다. 첫 중앙 검사는 현재 이력에서 실패했으며 원본 실패를 보존하고 normal 두 접점의 실제 국소 진단을 완료한 뒤 진행했다. 국소 진단기는 기존 파일이 있으면 덮어쓰지 않는다. Snapshot은 **두 왼쪽 원본을 어느 쪽도 수정하기 전에** 보존하고, `lower-development/left-central-inputs/snapshot-map.json`의 해시/경로 매핑으로 과거 중앙 기록을 구분한다. 충돌하는 기존 snapshot은 새 격리 worktree에서 처리한다.

왼쪽 정리는 고정된 높이별 새 wall/floor 영역에서만 이루어지며 원래 canonical 재료와 전체 male을 보존해야 한다. 일반형·자석형 모두 새 `left_central_relief` generation 계약과 실제 pre/post·floor·STEP/STL 검사를 완료해야 한다. 새 독립 left-only void 검토기는 producer와 별도로 치수를 재구성한다. 기존 frozen `review_kc2_lower_voids_v2 left`는 절삭 전 전체 wall을 요구하므로 수정된 왼쪽에는 사용하지 않는다. Phase A의 floor/magnetic-entry/stack/integrated central, Phase B의 두 left Fusion/native 및 파생 증거도 수정 후 새로 실행한다. 원래 중앙 실패나 이전 left native 보고서를 새 형상의 통과 근거로 재사용하지 않는다.

보호 대상 male은 `central-features.json`과 출력 SHA로 인증한 실제 `left-central-y95.step`, `left-central-y117.step` 각각이다. Y95의 원래 부착 뿌리는 부품 회피로 일부 제외되어 있으므로 nominal XY를 Z 전체로 돌출한 프리즘을 보존 기준으로 쓰면 안 된다. 그 잘못된 기준으로 첫 생성이 export 전에 중단된 기록은 [left attempt 1](diagnostics/left-central-attempt-1/failure.json)에 남겼다. 실제 두 기준 각각에 대해 before/after 누락이 정확히0이어야 하며, 전후 같은 비영 누락량을 허용하는 방식은 아니다. 절삭 계획의 nominal XY는 보수적인 보호 영역으로 유지한다.

## 5. 재생성 뒤 새 실제 증거

다음은 전체 명령을 한 번씩 복사하는 batch가 아니라 **순서별 CLI 예시**다. Phase A에서 모든 해당 조합의 source 실제 증거를 만든 뒤 Phase B의 Fusion/native, 마지막 Phase C의 전체 실제 envelope로 진행한다. 하나라도 실패하면 다음 완료 판정을 하지 않는다.

### Phase A: source CAD/STL와 조립

```powershell
python -B -m tools.review_kc2_profile_split_cad mx
python -B -m tools.review_kc2_registered_upper_direct mx
python -B -m tools.review_kc2_registered_upper_faces left mx
python -B -m tools.review_kc2_registered_mesh left mx
python -B -m tools.review_kc2_registered_mesh right mx
python -B -m tools.review_kc2_left_central_voids
python -B -m tools.review_kc2_lower_floor left
python -B -m tools.review_kc2_lower_floor left --magnetic
python -B -m tools.review_kc2_lower_floor right
python -B -m tools.review_kc2_lower_floor right --magnetic
python -B -m tools.review_kc2_floor_receiver
python -B -m tools.review_kc2_floor_receiver --magnetic
python -B -m tools.review_kc2_magnetic_entry left
python -B -m tools.review_kc2_registered_assembly left
python -B -m tools.review_kc2_integrated_central
```

Right profile actual review는 direct upper review의 선행 입력이다. 세 profile 모두 같은 순서로 수행한다. Left upper faces/mesh는 세 profile, floor/entry/assembly는 두 side에 필요하다. Left void는 새 left-only 검토기의 직접 V2 형식 보고서, right void는 위의 `right-receiver-strata-transfer.json` 경로다. 정리 후 원래 `right-void-review.json`을 재실행으로 덮어쓰지 않는다. Right의 최종 joint 검사는 `floor-capture-review.json` 두 개이며 과거 whole-height `split-review.json` 실패와 구별한다. 1.20 mm floor band의 실제 throat/ring/4방향 capture, 전체 male neck/head stock을 검사하되 일반 floor sealing/STL/조립 검사를 대신하지 않는다. 명령 실행의 정확한 전체 필수 결과 목록은 publisher의 `report_paths()`와 `jobs()`가 규정한다. 현재 배포의 MX supplemental 진단 이력을 새로운 direct review의 실행 결과로 가장하지 않는다.

Assembly는 해당 side의 세 upper BRep와 두 lower를 포함한 side-level void 증거를 모두 읽으므로 이들이 완료된 뒤 실행한다. Integrated central은 네 lower generation/STEP과 앞서 만든 central feature JSON/STEP을 읽는다. Right mesh도 세 profile 모두 필요하다.

### Phase B: Fusion과 native

Fusion 내부에서 `tools/fusion/KC2RegisteredHousingToF3D/KC2RegisteredHousingToF3D.py`의 `run('upper:left:mx')` 또는 `run('lower:left:normal')`을 호출한다. `runpy.run_path()`로 파일을 로드한 뒤 반환된 `run` 함수에 명시적인 job label을 전달할 수 있다. 일반 PowerShell Python에서 실행할 수 없다. 10개 job 각각 STEP→F3D→재열기→STEP readback을 완료한다. 여섯 upper 및 두 left lower는 다음 기존 검토기를 해당 label별로 사용한다.

```powershell
python -B -m tools.review_kc2_registered_native lower:left:normal
```

정리된 **right lower 두 개**는 별도 검토기를 사용한다. 기존 검토기는 옛 `right-void-review.json` 실패를 읽으므로 right lower에 사용하지 않는다.

```powershell
python -B -m tools.review_kc2_right_lower_native normal
python -B -m tools.review_kc2_right_lower_native magnetic
```

이 right 전용 검토기는 현재 `right-receiver-strata-transfer.json`의 전체 증거 연결을 검증한 뒤 실제 native readback과 최종 source STEP의 양방향 재료 차이를 검사한다. Fusion의 성공 상태만으로 이를 대신하지 않는다.

Receiver 정리로 바뀐 right 두 job은 Fusion export/reopen과 독립 native 검토도 새로 수행한다. 이전 native 파일을 새 STEP에 hash만 붙여 사용하지 않는다. Left void, lower floor, magnetic-entry 및 새 `review_kc2_floor_receiver`는 `--native` 직접 검사를 지원한다. 선택된 right void의 native 경로는 아래 조건부 transfer다.

```powershell
python -B -m tools.kc2_lower_native_transfer void right
python -B -m tools.kc2_lower_native_transfer floor right --kind normal
python -B -m tools.kc2_lower_native_transfer floor right --kind magnetic
python -B -m tools.kc2_lower_native_transfer floor-capture right --kind normal
python -B -m tools.kc2_lower_native_transfer floor-capture right --kind magnetic
python -B -m tools.kc2_lower_native_transfer magnetic-entry right
```

이는 해당 source 실제 증거와 필요한 모든 native body의 양방향 computed material difference가 **각각 정확히 0.0**일 때만 허용한다. Right void는 `right-receiver-strata-transfer.json`을 읽으며 이전 실패 V2나 중단612를 native PASS로 바꾸지 않는다. 이는 native feature 재실행이 아니며 작은 비영값에도 대체할 수 없다. 정확한 동등성이 없으면 source/native 차이를 진단하고 직접 검증 경로를 마련해야 하며 이 recipe만으로 완료할 수 없다. Source STL 결과는 source STL에 관한 증거로 남는다.

### Phase C: 전체 실제 envelope와 최종 gate

다음 검사는 **10개 job 모두**의 source BRep/void와 `native-review.json`, upper mesh, source joined-sweep 및 integrated central 보고서를 읽는다. 따라서 native보다 먼저 실행하면 선행 입력 누락으로 실패한다.

```powershell
python -B -m tools.review_kc2_actual_envelopes
```

마지막으로 현재 print-guide payload와 전체 실제 보고서가 모두 준비된 뒤 실행한다. 문서 입력도 publisher의 `PUBLICATION_DOCS`가 지정한 `.codex-tmp/registered-housing-fit/publication/...` 논리 경로에 필요하다. 배포된 대응 문서를 그 위치로 복사하여 source hash를 확인하고, 재생성 변경이 있으면 안내 내용부터 검토한다. 과거 `test-execution.json`을 복사해 완료 증거로 사용하지 않는다.

```powershell
python -B -m tools.kc2_registered_test_evidence
python -B -m tools.publish_kc2_registered_housings --preflight
```

격리 재생성은 새 source/output hash와 새 검증 기록을 만든다. 기존 release의 pass나 Fusion 파일 hash를 재사용하지 않는다. 이 문서는 `--publish`를 실행하지 않는다. 실물 마찰·강도·수축·접점·나사 토크·키캡 이동·RF는 별도 검증이며, 실리콘 발은 사용자 요청으로 현재 범위에서 보류되어 있다.

### STEP 게시 형식과 검증 원본

CAD 내보내기에서 나온 원본 STEP와 Fusion native-readback은 검증된 원래 바이트를 유지한다. 게시기는 편집용 STEP 10개에만 `kc2_step_whitespace.normalize`를 적용한다. 문자열·바이너리 리터럴·주석 안의 공백은 지우지 않으며, 보호된 구문 안에 줄 끝 공백이 있으면 임의로 바꾸지 않고 게시를 중단한다. 나머지 줄 끝 ASCII 공백/탭만 제거하고 모든 줄바꿈과 비삭제 바이트를 재구성해 원본과 정확히 일치해야 한다.

원본 10개는 게시 증거의 `raw-step/*.step.raw`로 보존한다. 이는 두 번째 활성 편집 모델이 아니라 기존 generation/형상/native 검사 SHA를 진실하게 유지하기 위한 원본 증거다. `hardware/MODELS`의 STEP는 정규화된 단일 편집본이고 STL/F3D는 이 형식 처리로 바꾸지 않는다. Manifest의 `step_normalization`은 고정된 10개 대응, 원본/게시본/코드 해시, 삭제량, `step_has_trailing_whitespace=false`와 구문 동일성을 기록한다. Portable 검증은 원본 바이트에서 변환을 다시 계산하고 게시본과 직접 비교하므로 형상 수치나 텍스트를 바꾼 뒤 출력 해시만 갱신하는 것으로 통과할 수 없다. 원본 generation/native SHA를 게시본 SHA로 덮어쓰지 않는다.

## 6. 실패·중단 이력의 Git 보존

Ignored `.codex-tmp`만으로는 clone 후 재현 가능한 Git 증거가 되지 않는다. 배포할 때 receiver snapshot의 필수 연결과 별도로, 두 `component-distance-attempt-*` 폴더의 `interrupted.json`, 해당 실행의 checker/helper/test 원본, attempt 2 priority 기록을 작은 versioned 진단 자료로 보존해야 한다. D8 원인분리 JSON과 그 정확한 실행 코드도 보존 대상이다. 이 문서의 작성만으로 그 복사·커밋이 끝난 것은 아니다.

권장 위치는 이 보고서 아래 `diagnostics/`이며, 진단 index에 원래 논리 경로→보존 상대 경로→SHA-256과 `interrupted_not_accepted`/`diagnosed_not_accepted` 의미를 적는다. 원본 JSON 내부 hash는 바꾸지 않는다. 원본 STEP는 이미 보존된 receiver snapshot 또는 manifest의 동일 hash 파일을 참조해 중복 복사를 피한다. 독립적인 역사적 진단 자료가 현재 PASS report 목록에 섞이지 않도록 하고, 시도1/2를 합쳐 가상의 완료612 목록을 만들지 않는다. 새 clone에서는 index의 실제 파일 hash와 snapshot alias를 검증할 수 있어야 한다.
