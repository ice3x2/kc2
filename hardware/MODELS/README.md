# 현재 하우징 · 보강판 · 어댑터

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

인쇄 전에 [현재 인쇄·조립 안내](PRINT-registered-housings.md)를 읽고 저장소 루트에서 다음 검증을 통과해야 합니다. manifest가 없거나 검증이 실패하면 인쇄를 보류하세요.

```powershell
python -B -m tools.publish_kc2_registered_housings --verify hardware/MODELS/kc2_registered_housing_manifest.json
```

Python 3.12와 Git 저장소가 필요합니다. 전체 CAD 검사·회귀시험의 Python 의존성은 저장소 `requirements-cad.txt`를 참고하세요. 과거 바이트 검증을 위해 기준 Git 커밋 `5b99bcb4567ea1c6bb4f17e54887d4de7614cd03`의 객체도 필요합니다. 기구 증거를 모두 게시한 뒤에는 `.codex-tmp` 없이 검증할 수 있습니다.

PCB는 이전처럼 **하판 받침 위에 올립니다**. 새 외벽은 PCB 가장자리를 여유 있게 감싸며 PCB를 압입하거나 외벽 위에 올리는 구조가 아닙니다. 기존 소켓 가림벽을 유지하고, 중앙의 좁은 세 구간에는 새 상승벽만 국소 생략합니다. 상하 위치맞춤 돌기·홈, 좌우 키보드의 비잠금 접촉부, 오른쪽 출력물 A/B 이음부를 서로 혼동하지 마세요.

- 상판은 MX / Choc V1 / 저상형 Deep Sea Mini 중 하나를 선택합니다. 해당 왼쪽 STL 한 개와 오른쪽 A/B STL 두 개를 인쇄합니다.
- 하판은 무자석 / magnetic 중 하나를 선택해 역시 세 STL을 인쇄합니다. 새 상판·새 하판을 함께 사용하고 과거 형상과 혼용하지 마세요.
- 정확한 15개 STL 링크, 스위치 종류, 나사 길이, 5.70 mm 브리지와 저상형 판 서포트 조건은 [현재 안내](PRINT-registered-housings.md)에 있습니다.
- STEP/F3D는 편집·확인용입니다. 오른쪽 전체 STEP/F3D는 두 솔리드를 포함하므로 150 mm 출력에는 A/B 분할 STL을 사용합니다.
- 기존 [링 어댑터 안내](adapters/README.md)와 파일은 이번 개정에서 변경하지 않습니다.

실제 출력 강도·끼움 힘·키캡 전체 이동·나사 토크·부품 편차는 디지털 검증만으로 합격 처리하지 않습니다. 실리콘 발 배치·접착 검토는 사용자 요청으로 보류되었으며 기존 발 그림은 이번 형상의 검증 증거가 아닙니다.

`PRINT-filled-plates.md` 및 이전 manifest/가이드는 현재 게시 검증을 대체하지 않습니다. 현재 manifest는 [kc2_registered_housing_manifest.json](kc2_registered_housing_manifest.json)이며 이전 버전은 Git 이력에 보존합니다. 이번 기구 개정은 기존 PCB/Gerber 16개 파일을 변경하거나 새 제조·주문을 승인하지 않습니다.
