-- ===========================================================================
-- 第四板块校验与查询视图（只在包含第 1–3 板块共享表的整合库中创建）
-- ===========================================================================

-- 第③板块评估中「可用于组包」的单元池：status='final' 且最终用途为 P01–P09。
-- final_purpose_id=10（拆解回收）不进入二次利用组包池。
CREATE VIEW V_PART4_ASSESSMENT_POOL AS
SELECT
    a.assessment_id,
    a.unit_id,
    a.status,
    a.final_purpose_id,
    up.purpose_code,
    a.final_score,
    a.assessment_time,
    u.registration_status,
    CASE WHEN a.status = 'final' AND a.final_purpose_id BETWEEN 1 AND 9
         THEN 1 ELSE 0 END AS is_assemblable
FROM ELIGIBILITY_ASSESSMENT a
JOIN battery_unit u ON u.unit_id = a.unit_id
LEFT JOIN USE_PURPOSE up ON up.purpose_id = a.final_purpose_id;

-- 各电池组当前（快照时点）仍在组内的成员及其采用的资格评估。
CREATE VIEW V_PART4_PACK_CURRENT_COMPOSITION AS
SELECT
    p.pack_id,
    p.pack_code,
    p.business_status,
    pu.pack_unit_id,
    pu.position_code,
    pu.unit_id,
    pu.assessment_id,
    a.status             AS assessment_status,
    a.final_purpose_id,
    pu.joined_at
FROM BATTERY_PACK p
JOIN BATTERY_PACK_UNIT pu ON pu.pack_id = p.pack_id
JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
WHERE pu.removed_at IS NULL;

-- 电池组当前业务状态 + 最近一次使用决定。
CREATE VIEW V_PART4_PACK_SERVICE_STATE AS
SELECT
    p.pack_id,
    p.pack_code,
    p.business_status,
    p.status_reason,
    (SELECT r.release_code FROM SERVICE_RELEASE r
      WHERE r.pack_id = p.pack_id
      ORDER BY r.decided_at DESC, r.release_code DESC LIMIT 1) AS latest_release_code,
    (SELECT r.purpose_id FROM SERVICE_RELEASE r
      WHERE r.pack_id = p.pack_id
      ORDER BY r.decided_at DESC, r.release_code DESC LIMIT 1) AS latest_purpose_id,
    (SELECT r.decision_result FROM SERVICE_RELEASE r
      WHERE r.pack_id = p.pack_id
      ORDER BY r.decided_at DESC, r.release_code DESC LIMIT 1) AS latest_decision_result,
    (SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
      WHERE pu.pack_id = p.pack_id AND pu.removed_at IS NULL) AS current_member_count
FROM BATTERY_PACK p;

-- 使用决定与其检查证据明细。
CREATE VIEW V_PART4_RELEASE_EVIDENCE AS
SELECT
    r.release_code,
    r.pack_id,
    r.purpose_id,
    r.decision_result,
    r.decided_at,
    r.composition_as_of,
    i.inspection_code,
    i.inspected_at,
    i.inspection_result,
    i.method_version
FROM SERVICE_RELEASE r
LEFT JOIN SERVICE_RELEASE_INSPECTION ri ON ri.release_code = r.release_code
LEFT JOIN PACK_INSPECTION i ON i.inspection_code = ri.inspection_code;

-- 审计：允许使用却没有同组同组成检查证据的决定（应为空）。
CREATE VIEW V_PART4_ALLOWED_RELEASE_WITHOUT_EVIDENCE AS
SELECT r.release_code, r.pack_id, r.decided_at
FROM SERVICE_RELEASE r
WHERE r.decision_result = 'allowed'
  AND NOT EXISTS (
      SELECT 1
      FROM SERVICE_RELEASE_INSPECTION ri
      JOIN PACK_INSPECTION i ON i.inspection_code = ri.inspection_code
      WHERE ri.release_code = r.release_code
        AND i.pack_id = r.pack_id
        AND i.composition_as_of = r.composition_as_of
        AND i.inspection_result IN ('pass', 'pass_with_observation'));

-- 审计：暂缓决定缺少缺失理由（应为空）。
CREATE VIEW V_PART4_DEFERRED_RELEASE_WITHOUT_REASON AS
SELECT release_code, pack_id, decided_at
FROM SERVICE_RELEASE
WHERE decision_result = 'deferred'
  AND (missing_evidence_reason IS NULL OR length(trim(missing_evidence_reason)) = 0);

-- 审计：检查证据的组成时点不在任何有效安装区间内（应为空）。
CREATE VIEW V_PART4_INSPECTION_EMPTY_COMPOSITION AS
SELECT i.inspection_code, i.pack_id, i.composition_as_of
FROM PACK_INSPECTION i
WHERE NOT EXISTS (
    SELECT 1 FROM BATTERY_PACK_UNIT pu
    WHERE pu.pack_id = i.pack_id
      AND pu.joined_at <= i.composition_as_of
      AND (pu.removed_at IS NULL OR pu.removed_at > i.composition_as_of));

-- 审计：同一电池组的成员评估用途不一致（应为空）。
CREATE VIEW V_PART4_PACK_MIXED_PURPOSE AS
SELECT pu.pack_id, COUNT(DISTINCT a.final_purpose_id) AS purpose_count
FROM BATTERY_PACK_UNIT pu
JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
GROUP BY pu.pack_id
HAVING COUNT(DISTINCT a.final_purpose_id) > 1;
