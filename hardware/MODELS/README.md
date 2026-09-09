# KC2 연속 벽 하우징 — 인쇄 파일 시작점

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`.

- [현재 인쇄·조립 안내](PRINT-enclosed.md): 하판 3개와 공통 MX 상판 3개 선택.
- [자석 홈 옵션](PRINT_magnetic.md): 무자석 또는 `_magnetic` 하판 중 한 세트 선택.
- [현재 게시 manifest](kc2_enclosure_manifest.json) · [검증 기록](../../docs/reports/enclosed-housing-20260909/README.md).
- [PCB·주문된 거버 위치](../README.md).

새 상판 벽은 하판 벽에 직접 닿고, 하판 외벽은 측면 소켓 공간을 가립니다.
USB·POWER 접근 홈, RESET 탐침 구멍과 오른쪽 A/B 조립 이음부는 필요한 예외입니다.
실제 파일이 안내와 일치하는지는 저장소 루트에서 확인하세요.

```powershell
python -B -m tools.publish_kc2_enclosure --verify
```

검증 실패나 manifest 부재 시 인쇄를 진행하지 마세요. 게시 검증 통과는 실제 프린터·부품 적합성의 보증이 아닙니다.
STL은 인쇄용, STEP과 실제 Fusion `.f3d`는 편집·확인용입니다.

이전 열린 r5 형상은 Git `cc854a3`의 과거 기록입니다. [PRINT-r5.md](PRINT-r5.md)는 현재 형상 안내가 아닙니다.
기존 하판 전용 생성기를 실행하면 열린 구조가 다시 생성될 수 있으므로 현재 모델의 재생성 절차로 사용하지 마세요.
`first_order_1to1` 도면은 주문 당시 PCB 기록이며 새 하우징 외곽·조립 검증을 대신하지 않습니다.
