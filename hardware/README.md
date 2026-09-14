# PCB · 주문한 거버 · 하우징 인쇄 파일

요구사항: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006/007`.

하우징을 인쇄하기 전에 [현재 인쇄·조립 안내](MODELS/PRINT-registered-housings.md)의 검증 명령을 실행하세요. 검증이 실패하거나 manifest가 없으면 인쇄를 보류합니다. 실제 끼움·강도·키캡 간섭·나사 토크는 출력·조립 후 확인해야 합니다.

- `PCB/`: 기존 주문 설계. [왼쪽 PCB](PCB/kc2_left/kc2_left.kicad_pcb), [오른쪽 PCB](PCB/kc2_right/kc2_right.kicad_pcb). 각 KiCad 프로젝트 폴더 전체와 저장소 `third_party` 라이브러리를 유지하세요.
- `GERBER/`: 변경하지 않은 주문 r4 PCB-only 패키지. [왼쪽 제조 ZIP](GERBER/kc2_left-pcb-fabrication-only.zip), [오른쪽 제조 ZIP](GERBER/kc2_right-pcb-fabrication-only.zip), [주문 manifest](GERBER/manifest.json). 이번 기구 개정으로 재주문할 필요는 없습니다.
- `MODELS/`: MX / Choc V1 / Deep Sea Mini 상판과 무자석 / magnetic 하판. 각 종류의 왼쪽 한 개와 오른쪽 A/B 두 STL을 사용합니다. 오른쪽 STEP/F3D는 두 부품을 포함하는 편집·확인용입니다.
- `MODELS/adapters/`: 이번에 변경하지 않은 [기존 링 어댑터](MODELS/adapters/README.md).

PCB는 이전처럼 하판 받침 위에 놓습니다. 새 외벽·상판 위치맞춤 홈, 중앙 접촉부, 오른쪽 A/B 결합부는 서로 다른 구조입니다. 이전 상판·하판과 새 파일을 섞지 말고 현재 안내의 정확한 15개 STL 링크 중 필요한 종류를 선택하세요.

실리콘 발 배치·접착 검토는 사용자 요청으로 보류했습니다. 예전 발 배치 그림은 이번 하우징의 검증 증거가 아닙니다. 기존 `PRINT-filled-plates.md` 등 과거 안내는 현재 게시 검증을 대체하지 않습니다. 현재 인쇄 안내가 이전 지침보다 우선합니다.

이 기구 개정은 이미 주문한 PCB/Gerber 16개 파일을 변경하지 않으며 새로운 제작·구매·결제 승인을 의미하지 않습니다.

