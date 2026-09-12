# KC2 하우징 — 내부 충전형 보강판

요구사항: `CON-ARCH-006`, `OPS-ARCH-006`.

[현재 인쇄·조립 안내](PRINT-filled-plates.md)를 먼저 확인하세요. 기존 하판 위에 PCB를 올리는 구조이며, 새 외벽 속에 PCB를 넣는 구조가 아닙니다.

- 하판은 무자석 또는 `_magnetic` 중 한 세트를 선택합니다.
- 두 하판 옵션 모두 MX, Choc V1, Deep Sea Mini 중 선택한 전용 상판과 조립합니다.
- 상판은 각 종류당 왼쪽 1개와 오른쪽 A/B 2개 STL을 사용합니다. 서로 다른 종류를 섞지 마세요.
- [게시 manifest](kc2_filled_plate_manifest.json)와 실제 파일이 일치해야 합니다.
- [내부 충전형 검증 기록](../../docs/reports/solid-filled-plates-20260913/README.md).

저장소 루트에서 `python -B -m tools.publish_kc2_filled_plates --verify`가 실패하면 인쇄를 보류하세요. STL은 인쇄용, STEP/F3D는 편집·확인용입니다. MX는 명목 7.50 mm, 저상형 두 종류는 명목 5.00 mm 나사를 사용하며 실제 출력·부품 공차는 별도 확인합니다.

기존 개별 r5 또는 국소 가림벽 생성기를 실행하면 현재 충전형을 덮어쓸 수 있습니다. 재생성은 현재 검증 기록의 절차를 따릅니다. 교체 전 보강 MX 상판은 Git `d9d3729`, 더 이전 r5는 `cc854a3`에 남아 있습니다. `PRINT-local-covers.md`와 이전 manifest는 과거 개정 기록이며 현재 상판 선택 기준이 아닙니다. `first_order_1to1` 도면은 주문 당시 PCB 기록이며 현재 하우징 조립 검증을 대신하지 않습니다.
