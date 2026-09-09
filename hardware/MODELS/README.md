# KC2 하우징 — 국소 가림벽 개정

요구사항: `CON-ARCH-006`, `OPS-ARCH-006`.

[현재 인쇄·조립 안내](PRINT-local-covers.md)를 먼저 확인하세요. 기존 하판 위에 PCB를 올리는 구조이며, 새 외벽 속에 PCB를 넣는 구조가 아닙니다.

- 하판은 무자석 또는 `_magnetic` 중 한 세트를 선택합니다.
- 두 옵션 모두 공통 MX 상판을 사용합니다.
- [게시 manifest](kc2_local_cover_manifest.json)와 실제 파일이 일치해야 합니다.
- [검증 기록](../../docs/reports/local-covers-20260910/README.md).

저장소 루트에서 `python -B -m tools.publish_kc2_local_covers --verify`가 실패하면 인쇄를 보류하세요. STL은 인쇄용, STEP/F3D는 편집·확인용입니다.

기존 개별 r5 생성기를 실행하면 가림부가 없는 형상으로 덮어쓸 수 있습니다. 새 가림부 재생성은 현재 검증 기록의 절차를 따릅니다. 과거 형상과 상세 manifest는 Git `cc854a3`에 남아 있습니다. `first_order_1to1` 도면은 주문 당시 PCB 기록이며 현재 하우징 조립 검증을 대신하지 않습니다.
