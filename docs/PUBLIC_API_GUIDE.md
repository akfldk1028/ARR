# 토지/건축 공공 API 가이드 (2026-02-24)

## 한줄 요약

PNU(19자리 필지코드) 하나로 **용도지역, 건폐율/용적률, 공시지가, 토지면적, 건축물대장**까지 전부 조회 가능. Vworld API key 하나면 Phase 3 핵심 기능 구현 가능.

---

## API Key 현황

| Key | 발급처 | 상태 | 용도 |
|-----|--------|------|------|
| `VWORLD_API_KEY` | vworld.kr | **발급 완료** (만료: 2026-08-24) | 지오코딩 + 토지이용계획 + 공시지가 + 토지특성 + 토지임야 |
| `DATA_GO_KR_SERVICE_KEY` | data.go.kr | **미발급** (Phase 3-P2) | 건축물대장 + 토지이용규제 + 실거래가 |
| `LAW_API_OC` | open.law.go.kr | **발급 완료** (`hanvit4303`) | 법률 다운로드 (사용중) |

**핵심**: Vworld key 하나로 Priority 1 전체 커버. data.go.kr key는 건축물대장부터 필요.

---

## 1. Vworld API (api.vworld.kr) — 핵심

**포털**: https://www.vworld.kr
**인증**: API key (무료, vworld.kr 회원가입 후 발급)
**호출제한**: 30,000건/일 (지오코딩), 데이터 API는 별도 제한 없음
**비용**: 무료
**포맷**: JSON (`format=json`)

### 1.1 지오코딩 (주소→좌표+PNU) ✅ 구현 완료

```
GET https://api.vworld.kr/req/address
  ?service=address&request=getCoord
  &key={VWORLD_API_KEY}
  &address={주소}
  &type=PARCEL  (or ROAD)
  &format=json&crs=EPSG:4326&refine=true
```

**응답 핵심**: `response.refined.structure.level4LC` → 19자리 PNU
**구현**: `land/services/pnu_resolver.py`
**테스트**: 6/6 지번주소 성공 (서초, 용인, 춘천, 나주, 분당, 강남)

### 1.2 토지이용계획 속성조회 ⭐ Phase 3 핵심

```
GET https://api.vworld.kr/ned/data/getLandUseAttr
  ?key={VWORLD_API_KEY}
  &pnu={19자리}
  &format=json
  &numOfRows=100
  &domain={등록도메인}
```

**PNU 지원**: Yes — `pnu` 파라미터에 19자리 그대로
**응답 핵심**:
- `prposAreaDstrcCodeNm`: **용도지역명** (예: "제1종일반주거지역") ← 이것이 핵심!
- `prposAreaDstrcCode`: 용도지역 코드
- `cnflcAt`: 저촉 여부
- `stdrYear`: 기준년도

**활용**: PNU → 용도지역 자동 조회. 현재 사용자가 `zones`를 수동 입력해야 하는 문제를 해결.
`land_api.py`의 stub을 이 API로 교체하면 **주소만 입력해도 건폐율/용적률이 자동 계산**됨.

### 1.3 개별공시지가

```
GET https://api.vworld.kr/ned/data/getIndvdLandPriceAttr
  ?key={VWORLD_API_KEY}
  &pnu={19자리}
  &stdrYear=2025
  &format=json
  &domain={등록도메인}
```

**응답 핵심**: `pblntfPclnd` (공시지가 원/m2), `stdrYear` (기준년도)
**활용**: `land_info.official_land_price` 필드 채움

### 1.4 토지임야정보 (토지대장)

```
GET https://api.vworld.kr/ned/data/ladfrlList
  ?key={VWORLD_API_KEY}
  &pnu={19자리}
  &format=json
  &domain={등록도메인}
```

**응답 핵심**: `lndAr` (면적 m2), `lndcgrCodeNm` (지목명)
**활용**: `land_info.land_area_m2` 필드 채움

### 1.5 토지특성정보

```
GET https://api.vworld.kr/ned/data/getLandCharacteristics
  ?key={VWORLD_API_KEY}
  &pnu={19자리}
  &stdrYear=2025
  &format=json
  &domain={등록도메인}
```

**응답 핵심**: 지목, 지형높이, 지형형상, 도로접면, 이용상황
**활용**: 토지 물리적 특성 → 건축 가능 여부 판단 보조

### 1.6 WMS/WFS (지도 서비스)

```
GET https://api.vworld.kr/req/wms
  ?service=WMS&version=1.3.0&request=GetMap
  &layers=lt_c_upisuq  (용도지역지구도)
  &key={VWORLD_API_KEY}
  &bbox={x1,y1,x2,y2}&width=512&height=512
  &format=image/png&crs=EPSG:4326
```

**주요 레이어**: 용도지역지구도(17종), 연속지적도, 토지이용계획도, 개발제한구역
**활용**: Frontend 지도 시각화 (Phase 4)

---

## 2. data.go.kr APIs

**포털**: https://www.data.go.kr
**인증**: ServiceKey (URL 파라미터, 무료)
**호출제한**: 개발 1,000건/일, 운영 10,000건/일 (신청시 증량)
**발급**: 회원가입 → API 활용신청 → 즉시~24시간 승인

### 2.1 건축물대장 ⭐⭐ 최고가치

```
GET http://apis.data.go.kr/1613000/BldRgstService_v2/getBrRecapTitleInfo
  ?serviceKey={KEY}
  &sigunguCd={PNU[0:5]}
  &bjdongCd={PNU[5:10]}
  &bun={PNU[11:15]}
  &ji={PNU[15:19]}
  &_type=json
```

**PNU 분해**: `sigunguCd`=PNU[0:5], `bjdongCd`=PNU[5:10], `bun`=PNU[11:15], `ji`=PNU[15:19]

**11개 오퍼레이션**:
| 오퍼레이션 | 설명 |
|-----------|------|
| `getBrRecapTitleInfo` | **총괄표제부** — bcRat(건폐율%), vlRat(용적률%), 대지면적, 연면적 |
| `getBrTitleInfo` | 표제부 — 동별 정보 |
| `getBrFlrOulnInfo` | 층별개요 |
| `getBrJijiguInfo` | **지역지구구역** — 해당 건물에 적용된 용도지역/지구/구역 |
| `getBrExposPubuseAreaInfo` | 전유공용면적 |
| `getBrBasisOvrInfo` | 기본개요 |
| `getBrOwnrInfo` | 소유자 |
| `getBrHsprcInfo` | 주택가격 |
| `getBrAtchJibunInfo` | 부속지번 |
| `getBrWclfInfo` | 오수정화시설 |
| `getBrExposInfo` | 전유부 |

**총괄표제부 핵심 응답**:
- `bcRat`: **기존 건물 실제 건폐율** (%)
- `vlRat`: **기존 건물 실제 용적률** (%)
- `platArea`: 대지면적 (m2)
- `archArea`: 건축면적 (m2)
- `totArea`: 연면적 (m2)
- `mainPurpsCdNm`: 주용도 (예: "공동주택")
- `hhldCnt`: 세대수
- `totPkngCnt`: 총주차수
- `useAprDay`: 사용승인일

**활용**: 기존 건축물의 **실제** 건폐율/용적률 확인. 신축시 비교 기준.

### 2.2 토지이용규제법령정보

```
GET https://apis.data.go.kr/1611000/LuArinfoService/attr/getLuArinfoAttrList
  ?ServiceKey={KEY}
  &ldCode={PNU[0:10]}
  &regstrSe={PNU[10]}
  &mnnm={PNU[11:15]}
  &slno={PNU[15:19]}
  &_type=json
```

**응답 핵심**: 해당 필지에 적용되는 모든 용도지역/지구/구역 + 관련법령 + 행위제한
**활용**: Vworld `getLandUseAttr`보다 법령 기반 규제 정보가 더 상세

### 2.3 토지이용규제정보서비스

```
GET https://apis.data.go.kr/1613000/arLandUseInfoService/DTarLandUseInfo
  ?serviceKey={KEY}
  &areaCd={시군구코드}
  &ucodeList={지역지구코드}
  &_type=json
```

**응답 핵심**: 행위제한 가능여부, 관련법령, 행위유형
**활용**: 용도지역별 구체적 행위제한 (건축, 개발행위 등)

### 2.4 토지소유정보

**Portal ID**: 15058047
**PNU 지원**: `pnu_code` 파라미터
**응답**: 소유구분(개인/법인/국유), 토지면적, 공시지가, 소유권변동일
**활용**: 국/공유지 여부 → 건축 가능 여부 판단

---

## 3. 실거래가 API (국토교통부)

```
GET http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev
  ?serviceKey={KEY}
  &LAWD_CD={PNU[0:5]}  (시군구코드)
  &DEAL_YMD=202602       (거래년월)
  &_type=json
```

**PNU 지원**: 간접 — `LAWD_CD`(PNU 앞 5자리, 시군구코드) + `DEAL_YMD`(년월)

**부동산 유형별 endpoint**:
| 유형 | Endpoint |
|------|----------|
| 아파트 매매 | `RTMSDataSvcAptTradeDev` |
| 아파트 전월세 | `RTMSDataSvcAptRentDev` |
| 단독/다가구 매매 | `RTMSDataSvcSHTradeDev` |
| 연립다세대 매매 | `RTMSDataSvcRHTradeDev` |
| 오피스텔 매매 | `RTMSDataSvcOffiTradeDev` |
| 토지 매매 | `RTMSDataSvcLandTradeDev` |
| 상업업무용 매매 | `RTMSDataSvcNrgTradeDev` |

**활용**: 주변 시세 참고 (직접 규제 분석과는 무관, Phase 5+ 부가기능)

---

## 4. 건축행정시스템 (세움터/건축HUB)

**포털**: https://www.eais.go.kr (세움터), https://open.eais.go.kr (데이터개방)
**API**: data.go.kr를 통해 발급/사용

**건축인허가정보**: 허가/착공/사용승인 이력
**PNU 지원**: 건축물대장과 동일 (`sigunguCd` + `bjdongCd` + `bun` + `ji`)
**활용**: 해당 필지의 건축 허가 이력, 건축 가능 여부 참고

---

## 5. 토지이음 (eum.go.kr)

**포털**: https://www.eum.go.kr
**특징**: 토지이용규제 **통합** 열람 (웹, API 직접 미제공)
**데이터**: SHP, CSV, PDF 파일 다운로드 가능
**활용**: 사용자 참고 링크, 검증용

---

## PNU 분해 규칙

PNU 19자리: `[시도2][시군구3][읍면동3][리2][토지구분1][본번4][부번4]`

```
예시: 4146513200102800003
      41  465  132  00  1  0280  0003
      시도 시군구 읍면동 리  대  본번  부번
```

| API | PNU 사용법 |
|-----|-----------|
| Vworld 전체 | `pnu=4146513200102800003` (19자리 그대로) |
| 건축물대장 | `sigunguCd=41465`, `bjdongCd=13200`, `bun=0280`, `ji=0003` |
| 토지이용규제법령 | `ldCode=4146513200`, `regstrSe=1`, `mnnm=0280`, `slno=0003` |
| 실거래가 | `LAWD_CD=41465` + `DEAL_YMD=YYYYMM` |

---

## Phase 3 구현 우선순위

### Priority 1 — Vworld key만으로 구현 가능 (key 이미 있음)

| API | 구현 내용 | 효과 |
|-----|----------|------|
| **토지이용계획** (`getLandUseAttr`) | PNU → 용도지역 자동 조회 | zones 수동 입력 불필요 |
| **토지임야정보** (`ladfrlList`) | PNU → 면적, 지목 | `land_area_m2` 자동 채움 |
| **개별공시지가** (`getIndvdLandPriceAttr`) | PNU → 공시지가 | `official_land_price` 자동 채움 |

→ `land_api.py` stub 교체만으로 **"주소 하나 입력 → 용도지역+건폐율+용적률+면적+공시지가+법조항" 전자동 분석** 완성

### Priority 2 — data.go.kr ServiceKey 필요

| API | 구현 내용 | 효과 |
|-----|----------|------|
| **건축물대장** 총괄표제부 | PNU → 실제 건폐율/용적률 | 기존 건물 비교 |
| **건축물대장** 지역지구구역 | PNU → 적용 용도지역/지구 | zones 교차 검증 |
| **토지이용규제법령** | PNU → 행위제한 상세 | 건축 가능 행위 구체화 |

### Priority 3 — 부가 기능

| API | 효과 |
|-----|------|
| 토지특성정보 | 경사도/도로접면 → 건축 가능성 |
| 토지소유정보 | 국공유지 여부 |
| 실거래가 | 주변 시세 |
| WMS/WFS | 지도 시각화 |

---

## NSDI → Vworld 이관 참고

2024년 1월부터 국가공간정보포털(NSDI) 서비스가 Vworld로 통합됨:

| 구 서비스 (nsdi) | 신 서비스 (Vworld) |
|-----------------|-------------------|
| `nsdi/LandCharacteristicsService` | `api.vworld.kr/ned/data/getLandCharacteristics` |
| `nsdi/IndvdLandPriceService` | `api.vworld.kr/ned/data/getIndvdLandPriceAttr` |
| `nsdi/eios/LadfrlService` | `api.vworld.kr/ned/data/ladfrlList` |
| `nsdi/LandUseService` | `api.vworld.kr/ned/data/getLandUseAttr` |

**결론**: Vworld API 사용 권장. 기존 NSDI endpoint도 일부 작동하나 Vworld가 공식.
