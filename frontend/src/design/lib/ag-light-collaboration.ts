import type { AGLightReview } from '../components/ag-light-flow/types';
import type { DesignEvidence } from './api-client';
import type { GeoJSONFeature, SetbackGeometriesMap } from './types';

export const COLLABORATION_STEPS = [
  { label: '1 법규', agent: 'law_graph_agent', output: 'Graph DB 조항·제약·누락 evidence' },
  { label: '2 주차', agent: 'parking_agent', output: '법정대수·연접·전면도로/차로 검토' },
  { label: '3 매스/디자인', agent: 'maas_geometry_agent', output: '법규를 만족하는 MAAS 형태·repair 근거' },
  { label: '4 최종검토', agent: 'review_agent', output: '통과/보류/실패와 남은 리스크' },
];

export type AgentTrace = AGLightReview & {
  refs: string[];
  formula?: string;
  decision: string;
};

const asRecord = (value: unknown): Record<string, unknown> => (
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
);

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asString = (value: unknown): string | undefined => (
  typeof value === 'string' && value.trim() ? value.trim() : undefined
);

const asNumber = (value: unknown): number | undefined => (
  typeof value === 'number' && Number.isFinite(value) ? value : undefined
);

const getNested = (source: unknown, path: string[]): unknown => (
  path.reduce<unknown>((current, key) => asRecord(current)[key], source)
);

const uniqueStrings = (values: unknown[], limit = 4): string[] => (
  Array.from(new Set(values
    .flatMap((value) => Array.isArray(value) ? value : [value])
    .map((value) => typeof value === 'string' ? value.trim() : '')
    .filter(Boolean)))
    .slice(0, limit)
);

const compactText = (value: unknown, fallback = '-'): string => {
  const text = typeof value === 'string'
    ? value
    : value == null
      ? ''
      : JSON.stringify(value);
  if (!text) return fallback;
  return text.length > 120 ? `${text.slice(0, 117)}...` : text;
};

const formatMetric = (value: number | undefined): string => (
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1) : '-'
);

export const statusColor = (status: AGLightReview['status']): string => {
  if (status === 'pass') return '#5eead4';
  if (status === 'fail') return '#fca5a5';
  if (status === 'check') return '#fbbf24';
  return '#93c5fd';
};

export const getMassLegalStatus = (
  evidence: DesignEvidence | null,
  massGeojson: GeoJSONFeature | null,
): string => {
  const props = asRecord(massGeojson?.properties);
  return asString(evidence?.final_status) || asString(props.legal_status) || 'unknown';
};

export const buildAgentTrace = (
  reviews: AGLightReview[],
  evidence: DesignEvidence | null,
  massGeojson: GeoJSONFeature | null,
  setbackGeometries?: SetbackGeometriesMap | null
): AgentTrace[] => {
  const props = asRecord(massGeojson?.properties);
  const evidenceCandidate = asRecord(evidence?.candidate);
  const checks = asArray(evidence?.checks).map(asRecord);
  const legal = asRecord(evidence?.legal);
  const lawArticles = asArray(legal.law_articles).map(asRecord);
  const graphProjection = asRecord(legal.graph_projection);
  const parking = asRecord(props.parking_precheck);
  const parkingFromEvidence = asRecord(getNested(evidence, ['mobility', 'parking', 'precheck']));
  const sourceParking = Object.keys(parking).length ? parking : parkingFromEvidence;
  const requiredCount = asRecord(sourceParking.required_count);
  const layout = asRecord(sourceParking.layout_candidate);
  const layoutFormula = asRecord(layout.layout_formula);
  const maasModel = asRecord(props.maas_model || evidenceCandidate.maas_model);
  const designQuality = asRecord(props.design_quality || maasModel.design_quality);
  const datum = asRecord(getNested(setbackGeometries, ['datum_result']));
  const sunlightEnvelope = asRecord(getNested(setbackGeometries, ['sunlight_envelope']));
  const massShape = asString(props.mass_shape) || asString(maasModel.operator) || asString(props.algorithm) || 'maas_legal_envelope';
  const verbSequence = uniqueStrings([
    asArray(props.maas_verb_sequence),
    asArray(maasModel.verb_sequence),
  ], 6);
  const lawRefs = uniqueStrings([
    lawArticles.map((article) => article.full_id || article.title || article.ref_id),
    checks.map((check) => asArray(asRecord(check.basis).law_articles)),
    checks.map((check) => asArray(check.evidence_refs)),
  ], 5);
  const lawCheckRefs = uniqueStrings(
    checks.map((check) => {
      const key = asString(check.key);
      const status = asString(check.status);
      return key ? `${key}${status ? `:${status}` : ''}` : '';
    }),
    5,
  );
  const finalDecision = asRecord(evidence?.final_decision);
  const missingDecisionEvidence = uniqueStrings(asArray(finalDecision.missing_evidence), 4);
  const parkingCheck = asRecord(checks.find((check) => check.key === 'parking_loading_and_mobility.parking_required_count') || {});
  const parkingRefs = uniqueStrings([
    requiredCount.selected_rule_id,
    requiredCount.base_rule_id,
    requiredCount.source_ordinance,
    requiredCount.source_appendix,
    parkingCheck.evidence_refs,
    asArray(asRecord(parkingCheck.basis).law_articles),
  ], 5);
  const qualityParts = [
    asNumber(designQuality.score) !== undefined ? `quality ${asNumber(designQuality.score)?.toFixed(3)}` : '',
    asString(designQuality.source),
    verbSequence.length ? `verbs ${verbSequence.join('->')}` : '',
  ].filter(Boolean);

  const reviewByAgent = new Map(reviews.map((review) => [review.agent, review]));
  const lawReview = reviewByAgent.get('law_agent');
  const parkingReview = reviewByAgent.get('parking_agent');
  const sunlightReview = reviewByAgent.get('sunlight_agent');
  const datumReview = reviewByAgent.get('datum_agent');
  const designReview = reviewByAgent.get('design_critic');

  return [
    {
      ...(lawReview || { agent: 'law_agent', label: '법규', status: 'check' as const, summary: '법규 근거 확인', detail: '' }),
      refs: lawRefs.length ? lawRefs : (lawCheckRefs.length ? lawCheckRefs : ['ARR legal constraint checks']),
      formula: graphProjection.available === true ? `Graph DB law refs ${graphProjection.resolved_count ?? lawRefs.length}건` : 'ARR constraint/evidence bundle',
      decision: compactText([
        `status=${getMassLegalStatus(evidence, massGeojson)}`,
        missingDecisionEvidence.length ? `missing=${missingDecisionEvidence.join(', ')}` : '',
      ].filter(Boolean).join(' · '), '법규 check/final_decision 기반'),
    },
    {
      ...(parkingReview || { agent: 'parking_agent', label: '주차', status: 'check' as const, summary: '주차 근거 확인', detail: '' }),
      refs: parkingRefs.length ? parkingRefs : ['parking_precheck.required_count/layout_candidate'],
      formula: compactText(requiredCount.rounding_rule || layoutFormula.module || layoutFormula.schema_version || layout.layout_formula, 'parking formula 확인 필요'),
      decision: compactText({
        required: requiredCount.required_spaces,
        provided: layout.provided_spaces,
        status: layout.status || sourceParking.status,
        strategy: sourceParking.selected_strategy || sourceParking.strategy || props.parking_strategy,
      }),
    },
    {
      ...(sunlightReview || { agent: 'sunlight_agent', label: '정북일조', status: 'info' as const, summary: '정북일조 envelope', detail: '' }),
      refs: uniqueStrings(['건축법 시행령 제86조', asString(sunlightEnvelope.datum_basis) || 'sunlight_envelope']),
      formula: compactText(sunlightEnvelope.slope ? `slope ${sunlightEnvelope.slope}` : 'H<=10m 직각 / H>10m 사선 envelope'),
      decision: compactText({
        applies: sunlightEnvelope.applies,
        datum_m: sunlightEnvelope.datum_m || datum.datum_elevation_m || datum.elevation_m,
      }),
    },
    {
      ...(datumReview || { agent: 'datum_agent', label: '대지레벨', status: 'check' as const, summary: 'datum 확인', detail: '' }),
      refs: uniqueStrings(['건축법 시행령 §119', '건축법 시행령 §86', asString(datum.elevation_source)]),
      formula: compactText(datum.basis || datum.datum_basis || '대지/도로/인접대지 평균 기준면 분리'),
      decision: compactText({
        parcel: datum.parcel_datum_m,
        road: datum.road_datum_m,
        neighbor: datum.neighbor_datum_m,
        selected: datum.datum_elevation_m || datum.elevation_m,
      }),
    },
    {
      ...(designReview || { agent: 'design_critic', label: '디자인', status: 'info' as const, summary: '매스 판단', detail: '' }),
      refs: [massShape, ...verbSequence],
      formula: qualityParts.join(' · ') || 'MAAS legal morphology ranking',
      decision: compactText({
        shape: massShape,
        far: props.far,
        bcr: props.bcr,
        height: props.height,
        reason: props.design_reason || props.rank_reason || designQuality.reason,
      }),
    },
  ];
};

export const makeAgentReviews = (
  evidence: DesignEvidence | null,
  massGeojson: GeoJSONFeature | null,
  setbackGeometries?: SetbackGeometriesMap | null
): AGLightReview[] => {
  const props = asRecord(massGeojson?.properties);
  const evidenceCandidate = asRecord(evidence?.candidate);
  const parking = asRecord(props.parking_precheck);
  const evidenceParking = asRecord(evidenceCandidate.parking_precheck);
  const layoutCandidate = asRecord(parking.layout_candidate);
  const evidenceLayoutCandidate = asRecord(evidenceParking.layout_candidate);
  const requiredCount = asRecord(parking.required_count);
  const evidenceRequiredCount = asRecord(evidenceParking.required_count);
  const sourceParking = Object.keys(parking).length > 0 ? parking : evidenceParking;
  const requiredParking = asNumber(sourceParking.required)
    ?? asNumber(sourceParking.required_spaces)
    ?? asNumber(requiredCount.required_spaces)
    ?? asNumber(evidenceRequiredCount.required_spaces)
    ?? asNumber(layoutCandidate.required_spaces)
    ?? asNumber(evidenceLayoutCandidate.required_spaces);
  const providedParking = asNumber(sourceParking.provided)
    ?? asNumber(sourceParking.provided_spaces)
    ?? asNumber(layoutCandidate.provided_spaces)
    ?? asNumber(evidenceLayoutCandidate.provided_spaces);
  const parkingStrategy = String(
    sourceParking.selected_strategy
    || sourceParking.strategy
    || layoutCandidate.strategy
    || evidenceLayoutCandidate.strategy
    || evidenceCandidate.parking_strategy
    || props.parking_strategy
    || 'unknown',
  );
  const finalStatus = String(evidence?.final_status || props.legal_status || 'evidence_loaded');
  const hardFailures = asArray(evidence?.hard_failures);
  const missingEvidence = asArray(evidence?.missing_evidence);
  const openIssues = asArray(evidence?.open_issues);
  const datum = asRecord(getNested(setbackGeometries, ['datum_result']));
  const sunlightEnvelope = asRecord(getNested(setbackGeometries, ['sunlight_envelope']));
  const sunlightApplies = Object.keys(sunlightEnvelope).length > 0
    && sunlightEnvelope.applies !== false
    && sunlightEnvelope.enabled !== false;
  const datumElevation = asNumber(datum.datum_elevation_m)
    ?? asNumber(datum.sunlight_datum_m)
    ?? asNumber(datum.average_level_m)
    ?? asNumber(datum.elevation_m)
    ?? asNumber(datum.parcel_datum_m);
  const datumSource = typeof datum.elevation_source === 'string' ? datum.elevation_source : 'datum_result';
  const far = asNumber(props.far);
  const bcr = asNumber(props.bcr);
  const height = asNumber(props.height);

  const parkingStatus: AGLightReview['status'] = requiredParking && providedParking !== undefined
    ? (providedParking >= requiredParking ? 'pass' : 'fail')
    : 'check';
  const lawStatus: AGLightReview['status'] = hardFailures.length > 0 || finalStatus.toLowerCase().includes('fail')
    ? 'fail'
    : (missingEvidence.length > 0 || openIssues.length > 0 ? 'check' : 'pass');

  return [
    {
      agent: 'law_agent',
      label: '법규',
      status: lawStatus,
      summary: `최종 ${finalStatus}`,
      detail: `hard ${hardFailures.length} · missing ${missingEvidence.length} · issue ${openIssues.length}`,
    },
    {
      agent: 'parking_agent',
      label: '주차',
      status: parkingStatus,
      summary: requiredParking !== undefined && providedParking !== undefined
        ? `${providedParking}/${requiredParking}대 · ${parkingStrategy}`
        : '주차 산정 근거 확인 필요',
      detail: '소규모 배치는 전면도로 이용 가능성을 별도 connector 없이 선형 주차면으로 검토',
    },
    {
      agent: 'sunlight_agent',
      label: '정북일조',
      status: sunlightApplies ? 'pass' : 'info',
      summary: sunlightApplies ? '§86 envelope 적용' : '적용 외 또는 envelope 없음',
      detail: datumElevation !== undefined ? `기준면 ${datumElevation.toFixed(2)}m 기반` : '기준면 수치 확인 필요',
    },
    {
      agent: 'datum_agent',
      label: '대지레벨',
      status: datumElevation !== undefined ? 'pass' : 'check',
      summary: datumElevation !== undefined ? `${datumSource} 기준면 ${datumElevation.toFixed(2)}m` : 'datum_result 없음',
      detail: '§119 가중평균 및 §86 인접대지 평균 기준 분리 검토',
    },
    {
      agent: 'design_critic',
      label: '디자인',
      status: 'info',
      summary: `FAR ${formatMetric(far)} · BCR ${formatMetric(bcr)} · H ${formatMetric(height)}m`,
      detail: '법규 매스 고정 후 형태, 주차 가독성, 외관 생성만 후속 검토',
    },
  ];
};
