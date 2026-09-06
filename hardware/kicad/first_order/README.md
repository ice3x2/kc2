# KC2 PCB 제조 패키지

요구사항: `CON-ARCH-004/006/007`, `REL-ARCH-001`, `OPS-ARCH-007`.

> 현재 개정: 바닥 일체형 `solid-floor-20260907-r4`. 디지털 설계·출력 검증 완료; 실물 합격은 별도입니다.

디렉토리 구조, 정확한 주문 ZIP·인쇄 STL·실리콘 발 배치·조립 순서는
프로젝트 루트의 **[order.md](../../../order.md)**를 기준으로 확인하세요.
요구사항 원본은 [SRS](../../../docs/spec/00.index.md)입니다.

## 새 개정의 파일 경로

- [왼쪽 PCB ZIP](solid-floor-20260907-r4/kc2_left-pcb-fabrication-only.zip)
- [오른쪽 PCB ZIP](solid-floor-20260907-r4/kc2_right-pcb-fabrication-only.zip)
- [제조 설정](solid-floor-20260907-r4/fabrication-profile.json)
- [왼쪽 수동 BOM](solid-floor-20260907-r4/kc2_left-manual-mx-bom.json) / [오른쪽 BOM](solid-floor-20260907-r4/kc2_right-manual-mx-bom.json)
- [검증·해시 manifest](solid-floor-20260907-r4/manifest.json)

r4는 PCB 배선·거버 바이트를 변경하지 않고 하판에 1.20 mm 바닥과 조각당 Ø8 mm 실리콘 발 접착면 4곳을 추가합니다.
PCB 높이와 나사 받침은 유지하므로 명목 M1.4×7.50 mm 나사를 길게 바꾸지 않습니다.
바닥 아래로 납땜할 수 없으므로 PCB를 분리한 상태에서 납땜하고, 실제 하부 돌출을 최대 2.90 mm 이내로 확인합니다.

PCB 제조만 요청하는 패키지입니다. BOM/CPL 자동 실장 업로드나 주문·결제를 실행하지 않았습니다.
접점 공차, 인쇄 강도, 실리콘 접착·미끄럼 성능, 실제 배터리·충전 온도·무선 합격은 수령 후 확인해야 합니다.

```powershell
& C:/Python312/python.exe -B -m tools.prepare_kc2_first_order --verify-package hardware/kicad/first_order/solid-floor-20260907-r4
```

## 보존된 과거 개정

| 디렉토리 | 의미 |
|---|---|
| [v1-recess-20260906-r3](v1-recess-20260906-r3/) | V1 구멍·매립 나사 상판, 개방 하판 당시 봉인본 |
| [mx-receptacle-20260906-r2](mx-receptacle-20260906-r2/) | 이전 MX 검토 개정 |
| [mx-receptacle-20260906](mx-receptacle-20260906/) | 최초 MX 검토 개정 |

과거 패키지는 수정하지 않습니다. 이전 `first_order_ready`는 당시의 소스에 대한 기록이며 현재 변경된 하우징까지 승인하지 않습니다.
현재 소스로 과거 패키지를 검증하면 소스 해시 차이가 날 수 있습니다. 과거 파일이나 `../fabrication/`을 현재 주문에 혼용하지 마세요.
