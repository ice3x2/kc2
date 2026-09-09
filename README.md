# kc2

- **[최신 PCB · 주문한 거버 · 인쇄 모델 — hardware](hardware/README.md)**
- [PCB 프로젝트](hardware/PCB/) · [주문한 거버 ZIP](hardware/GERBER/) · [하우징·링 모델](hardware/MODELS/)
- [국소 가림벽 인쇄 안내](hardware/MODELS/PRINT-local-covers.md) · [검증 기록](docs/reports/local-covers-20260910/README.md)
- [자석 홈 옵션 / 무자석 옵션 선택 안내](hardware/MODELS/PRINT_magnetic.md)
- [주문 당시 안내 원본](order.md) — 봉인 해시 보존용입니다. 현재 위치는 위 `hardware` 안내를 보세요.
- [요구사항 원본(SRS)](docs/spec/00.index.md)

새로 clone한 뒤 기존 생성·검증 도구를 사용할 때는 한 번 실행하세요(Python 3.12 이상).

```powershell
python -B -m tools.kc2_current_layout --apply
```

현재 파일은 `hardware/PCB`, `hardware/GERBER`, `hardware/MODELS`에 실제로 저장됩니다. 기존 `hardware/case`와 일부 `hardware/kicad` 경로는 동일 원본을 가리키는 로컬 호환 연결이며 복사본이 아닙니다.
