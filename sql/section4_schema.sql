-- ===========================================================================
-- IBA6151 电池护照项目 · 第四板块「组包与维护管理」SQLite 逻辑模式
-- ---------------------------------------------------------------------------
-- 适用：先载入第 1–3 板块共享表（organization / battery_unit /
--       lifecycle_event / ELIGIBILITY_ASSESSMENT / USE_PURPOSE 等）的整合库，
--       再执行本文件。上游表由第①–③板块维护，本文件只新增第四板块的 7 张表。
--
-- 约定：
--   * 实现平台 PostgreSQL 为课程最终平台；本 SQLite 版本用于小组数据阶段
--     的可执行数据快照与合库校验（与第 1–3 板块交付方式一致）。
--   * 时间列使用 TEXT，格式固定为 'YYYY-MM-DDTHH:MM:SS+08:00'（Asia/Shanghai）。
--   * 业务记录一律 data_origin = 'synthetic'；引用的单元、检测、评估数据
--     保留其原有来源标签，不在本板块改写。
--   * 所有「允许使用」决定必须引用同组、同组成的检查证据；该跨表规则由
--     本文件末尾的校验视图和 scripts/validate_section4_data.py 检查。
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 4.1 电池组 BATTERY_PACK
-- ---------------------------------------------------------------------------
CREATE TABLE BATTERY_PACK (
    pack_id             TEXT PRIMARY KEY,
    pack_code           TEXT NOT NULL UNIQUE
                            CHECK (pack_code GLOB 'SIM-PACK-[0-9][0-9][0-9][0-9]'),
    model_name          TEXT NOT NULL CHECK (length(trim(model_name)) > 0),
    formed_at           TEXT,
    design_requirements TEXT NOT NULL CHECK (length(trim(design_requirements)) > 0),
    nameplate_ratings   TEXT NOT NULL CHECK (length(trim(nameplate_ratings)) > 0),
    business_status     TEXT NOT NULL CHECK (business_status IN (
                            'pending_inspection', 'available',
                            'in_maintenance', 'restricted', 'retired')),
    status_reason       TEXT,
    data_origin         TEXT NOT NULL CHECK (data_origin = 'synthetic'),
    recorded_at         TEXT NOT NULL,
    source_ref          TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    CHECK (formed_at IS NULL OR (length(formed_at) = 25 AND julianday(formed_at) IS NOT NULL)),
    CHECK (length(recorded_at) = 25 AND julianday(recorded_at) IS NOT NULL),
    CHECK (business_status NOT IN ('in_maintenance', 'restricted', 'retired')
           OR (status_reason IS NOT NULL AND length(trim(status_reason)) > 0))
);

-- ---------------------------------------------------------------------------
-- 4.2 成员安装 BATTERY_PACK_UNIT
--     一条记录 = 某单元在某组某位置的一次安装发生，用半开区间
--     [joined_at, removed_at) 表示有效期；removed_at 为空表示仍在组内。
-- ---------------------------------------------------------------------------
CREATE TABLE BATTERY_PACK_UNIT (
    pack_unit_id              INTEGER PRIMARY KEY,
    pack_id                   TEXT NOT NULL REFERENCES BATTERY_PACK (pack_id),
    unit_id                   TEXT NOT NULL REFERENCES battery_unit (unit_id),
    occurrence_no             INTEGER NOT NULL CHECK (occurrence_no >= 1),
    assessment_id             INTEGER REFERENCES ELIGIBILITY_ASSESSMENT (assessment_id),
    position_code             TEXT NOT NULL CHECK (length(trim(position_code)) > 0),
    joined_at                 TEXT NOT NULL,
    removed_at                TEXT,
    join_reason               TEXT NOT NULL CHECK (length(trim(join_reason)) > 0),
    remove_reason             TEXT,
    join_order                INTEGER CHECK (join_order IS NULL OR join_order >= 1),
    remove_order              INTEGER CHECK (remove_order IS NULL OR remove_order >= 1),
    added_by_job_code         TEXT REFERENCES ASSEMBLY_JOB (job_code),
    added_by_maintenance_id   TEXT REFERENCES MAINTENANCE_EVENT (maintenance_id),
    removed_by_job_code       TEXT REFERENCES ASSEMBLY_JOB (job_code),
    removed_by_maintenance_id TEXT REFERENCES MAINTENANCE_EVENT (maintenance_id),
    source_missing_reason     TEXT,
    data_origin               TEXT NOT NULL CHECK (data_origin = 'synthetic'),
    recorded_at               TEXT NOT NULL,
    source_ref                TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    UNIQUE (pack_id, unit_id, occurrence_no),
    CHECK (length(joined_at) = 25 AND julianday(joined_at) IS NOT NULL),
    CHECK (removed_at IS NULL OR (length(removed_at) = 25 AND julianday(removed_at) IS NOT NULL)),
    CHECK (length(recorded_at) = 25 AND julianday(recorded_at) IS NOT NULL),
    CHECK (removed_at IS NULL OR julianday(removed_at) > julianday(joined_at)),
    CHECK (removed_at IS NOT NULL OR (
        remove_reason IS NULL AND remove_order IS NULL
        AND removed_by_job_code IS NULL AND removed_by_maintenance_id IS NULL)),
    CHECK (removed_at IS NULL OR remove_reason IS NOT NULL),
    CHECK (source_missing_reason IS NULL OR length(trim(source_missing_reason)) > 0),
    -- 本板块生成的成员记录均为合成的新装/换入，必须能追溯到第③板块的最终评估。
    CHECK (data_origin <> 'synthetic' OR assessment_id IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- 4.3 实际组装作业 ASSEMBLY_JOB
-- ---------------------------------------------------------------------------
CREATE TABLE ASSEMBLY_JOB (
    job_code          TEXT PRIMARY KEY
                          CHECK (job_code GLOB 'SIM-JOB-[0-9][0-9][0-9][0-9]'),
    pack_id           TEXT NOT NULL REFERENCES BATTERY_PACK (pack_id),
    executor_org_id   TEXT NOT NULL REFERENCES organization (organization_id),
    maintenance_id    TEXT REFERENCES MAINTENANCE_EVENT (maintenance_id),
    job_type          TEXT NOT NULL CHECK (job_type IN ('initial_assembly', 'reassembly')),
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    process_summary   TEXT NOT NULL CHECK (length(trim(process_summary)) > 0),
    execution_result  TEXT,
    data_origin       TEXT NOT NULL CHECK (data_origin = 'synthetic'),
    recorded_at       TEXT NOT NULL,
    source_ref        TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    CHECK (length(started_at) = 25 AND julianday(started_at) IS NOT NULL),
    CHECK (ended_at IS NULL OR (length(ended_at) = 25 AND julianday(ended_at) IS NOT NULL)),
    CHECK (length(recorded_at) = 25 AND julianday(recorded_at) IS NOT NULL),
    CHECK (ended_at IS NULL OR julianday(ended_at) > julianday(started_at)),
    CHECK (ended_at IS NULL OR (execution_result IS NOT NULL
                                AND length(trim(execution_result)) > 0))
);

-- ---------------------------------------------------------------------------
-- 4.4 实际维护事件 MAINTENANCE_EVENT
--     共享事件模型的维护子类型：maintenance_id 即父事件 lifecycle_event.event_id。
--     目标组、执行组织、发生/录入时间与来源由父事件承载，本表只存维护专属信息。
-- ---------------------------------------------------------------------------
CREATE TABLE MAINTENANCE_EVENT (
    maintenance_id   TEXT PRIMARY KEY REFERENCES lifecycle_event (event_id),
    maintenance_type TEXT NOT NULL CHECK (maintenance_type IN (
                         'component_replacement', 'fault_repair',
                         'periodic_service', 'fault_diagnosis')),
    problem_summary  TEXT NOT NULL CHECK (length(trim(problem_summary)) > 0),
    action_summary   TEXT NOT NULL CHECK (length(trim(action_summary)) > 0),
    execution_result TEXT CHECK (execution_result IS NULL
                                 OR execution_result IN ('completed', 'failed'))
);

-- ---------------------------------------------------------------------------
-- 4.5 组级检查 PACK_INSPECTION
-- ---------------------------------------------------------------------------
CREATE TABLE PACK_INSPECTION (
    inspection_code             TEXT PRIMARY KEY
                                    CHECK (inspection_code GLOB 'SIM-INSP-[0-9][0-9][0-9][0-9][0-9]'),
    pack_id                     TEXT NOT NULL REFERENCES BATTERY_PACK (pack_id),
    inspector_org_id            TEXT NOT NULL REFERENCES organization (organization_id),
    triggered_by_job_code       TEXT REFERENCES ASSEMBLY_JOB (job_code),
    triggered_by_maintenance_id TEXT REFERENCES MAINTENANCE_EVENT (maintenance_id),
    inspected_at                TEXT NOT NULL,
    composition_as_of           TEXT NOT NULL,
    composition_order           INTEGER CHECK (composition_order IS NULL OR composition_order >= 1),
    method_ref                  TEXT NOT NULL CHECK (length(trim(method_ref)) > 0),
    method_version              TEXT NOT NULL CHECK (length(trim(method_version)) > 0),
    observation_summary         TEXT NOT NULL CHECK (length(trim(observation_summary)) > 0),
    inspection_result           TEXT NOT NULL CHECK (inspection_result IN (
                                    'pass', 'pass_with_observation', 'fail')),
    report_ref                  TEXT NOT NULL CHECK (length(trim(report_ref)) > 0),
    requirements_snapshot_or_ref TEXT NOT NULL
                                    CHECK (length(trim(requirements_snapshot_or_ref)) > 0),
    data_origin                 TEXT NOT NULL CHECK (data_origin = 'synthetic'),
    recorded_at                 TEXT NOT NULL,
    source_ref                  TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    CHECK (length(inspected_at) = 25 AND julianday(inspected_at) IS NOT NULL),
    CHECK (length(composition_as_of) = 25 AND julianday(composition_as_of) IS NOT NULL),
    CHECK (length(recorded_at) = 25 AND julianday(recorded_at) IS NOT NULL),
    CHECK (julianday(composition_as_of) <= julianday(inspected_at)),
    -- 一次检查至多一个主要触发来源；定期检查可以两个都为空。
    CHECK (triggered_by_job_code IS NULL OR triggered_by_maintenance_id IS NULL)
);

-- ---------------------------------------------------------------------------
-- 4.6 业务使用决定 SERVICE_RELEASE
-- ---------------------------------------------------------------------------
CREATE TABLE SERVICE_RELEASE (
    release_code             TEXT PRIMARY KEY
                                 CHECK (release_code GLOB 'SIM-REL-[0-9][0-9][0-9][0-9][0-9]'),
    pack_id                  TEXT NOT NULL REFERENCES BATTERY_PACK (pack_id),
    responsible_org_id       TEXT NOT NULL REFERENCES organization (organization_id),
    purpose_id               INTEGER NOT NULL REFERENCES USE_PURPOSE (purpose_id),
    purpose_basis_version    TEXT NOT NULL CHECK (length(trim(purpose_basis_version)) > 0),
    decided_at               TEXT NOT NULL,
    composition_as_of        TEXT NOT NULL,
    composition_order        INTEGER CHECK (composition_order IS NULL OR composition_order >= 1),
    decision_result          TEXT NOT NULL CHECK (decision_result IN (
                                 'allowed', 'rejected', 'deferred')),
    decision_reason          TEXT NOT NULL CHECK (length(trim(decision_reason)) > 0),
    use_restrictions         TEXT,
    missing_evidence_reason  TEXT,
    data_origin              TEXT NOT NULL CHECK (data_origin = 'synthetic'),
    recorded_at              TEXT NOT NULL,
    source_ref               TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    CHECK (length(decided_at) = 25 AND julianday(decided_at) IS NOT NULL),
    CHECK (length(composition_as_of) = 25 AND julianday(composition_as_of) IS NOT NULL),
    CHECK (length(recorded_at) = 25 AND julianday(recorded_at) IS NOT NULL),
    CHECK (julianday(composition_as_of) <= julianday(decided_at)),
    CHECK (use_restrictions IS NULL OR length(trim(use_restrictions)) > 0),
    CHECK (missing_evidence_reason IS NULL OR length(trim(missing_evidence_reason)) > 0),
    -- 因检查证据缺失而暂缓时必须写明缺口。
    CHECK (decision_result <> 'deferred' OR missing_evidence_reason IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- 4.7 使用决定检查证据 SERVICE_RELEASE_INSPECTION
-- ---------------------------------------------------------------------------
CREATE TABLE SERVICE_RELEASE_INSPECTION (
    release_code    TEXT NOT NULL REFERENCES SERVICE_RELEASE (release_code),
    inspection_code TEXT NOT NULL REFERENCES PACK_INSPECTION (inspection_code),
    PRIMARY KEY (release_code, inspection_code)
);

-- ---------------------------------------------------------------------------
-- 索引
-- ---------------------------------------------------------------------------
CREATE INDEX idx_part4_pack_unit_pack       ON BATTERY_PACK_UNIT (pack_id, joined_at);
CREATE INDEX idx_part4_pack_unit_unit       ON BATTERY_PACK_UNIT (unit_id, joined_at);
CREATE INDEX idx_part4_pack_unit_assessment ON BATTERY_PACK_UNIT (assessment_id);
CREATE INDEX idx_part4_job_pack             ON ASSEMBLY_JOB (pack_id, started_at);
CREATE INDEX idx_part4_job_maintenance      ON ASSEMBLY_JOB (maintenance_id);
CREATE INDEX idx_part4_inspection_pack      ON PACK_INSPECTION (pack_id, inspected_at);
CREATE INDEX idx_part4_inspection_compo     ON PACK_INSPECTION (pack_id, composition_as_of);
CREATE INDEX idx_part4_release_pack         ON SERVICE_RELEASE (pack_id, decided_at);
CREATE INDEX idx_part4_release_purpose      ON SERVICE_RELEASE (purpose_id);
CREATE INDEX idx_part4_release_evidence     ON SERVICE_RELEASE_INSPECTION (inspection_code);
CREATE INDEX idx_part4_lifecycle_pack       ON lifecycle_event (battery_pack_id, occurred_at);

-- ---------------------------------------------------------------------------
-- 触发器：成员安装的来源、同组一致性与时间不重叠
-- ---------------------------------------------------------------------------
CREATE TRIGGER part4_pack_unit_add_source_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN ((NEW.added_by_job_code IS NOT NULL) + (NEW.added_by_maintenance_id IS NOT NULL)) <> 1
     AND (NEW.source_missing_reason IS NULL OR length(trim(NEW.source_missing_reason)) = 0)
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: add needs exactly one source, or source_missing_reason');
END;

CREATE TRIGGER part4_pack_unit_add_source_update
BEFORE UPDATE OF added_by_job_code, added_by_maintenance_id, source_missing_reason
ON BATTERY_PACK_UNIT
WHEN ((NEW.added_by_job_code IS NOT NULL) + (NEW.added_by_maintenance_id IS NOT NULL)) <> 1
     AND (NEW.source_missing_reason IS NULL OR length(trim(NEW.source_missing_reason)) = 0)
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: add needs exactly one source, or source_missing_reason');
END;

CREATE TRIGGER part4_pack_unit_remove_source_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN NEW.removed_at IS NOT NULL
     AND ((NEW.removed_by_job_code IS NOT NULL) + (NEW.removed_by_maintenance_id IS NOT NULL)) <> 1
     AND (NEW.source_missing_reason IS NULL OR length(trim(NEW.source_missing_reason)) = 0)
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: removal needs exactly one source, or source_missing_reason');
END;

CREATE TRIGGER part4_pack_unit_remove_source_update
BEFORE UPDATE OF removed_by_job_code, removed_by_maintenance_id, removed_at, source_missing_reason
ON BATTERY_PACK_UNIT
WHEN NEW.removed_at IS NOT NULL
     AND ((NEW.removed_by_job_code IS NOT NULL) + (NEW.removed_by_maintenance_id IS NOT NULL)) <> 1
     AND (NEW.source_missing_reason IS NULL OR length(trim(NEW.source_missing_reason)) = 0)
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: removal needs exactly one source, or source_missing_reason');
END;

CREATE TRIGGER part4_pack_unit_source_same_pack_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN (NEW.added_by_job_code IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM ASSEMBLY_JOB j
          WHERE j.job_code = NEW.added_by_job_code AND j.pack_id = NEW.pack_id))
  OR (NEW.added_by_maintenance_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM MAINTENANCE_EVENT m
          JOIN lifecycle_event e ON e.event_id = m.maintenance_id
          WHERE m.maintenance_id = NEW.added_by_maintenance_id
            AND e.battery_pack_id = NEW.pack_id))
  OR (NEW.removed_by_job_code IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM ASSEMBLY_JOB j
          WHERE j.job_code = NEW.removed_by_job_code AND j.pack_id = NEW.pack_id))
  OR (NEW.removed_by_maintenance_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM MAINTENANCE_EVENT m
          JOIN lifecycle_event e ON e.event_id = m.maintenance_id
          WHERE m.maintenance_id = NEW.removed_by_maintenance_id
            AND e.battery_pack_id = NEW.pack_id))
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: change source must belong to the same pack');
END;

CREATE TRIGGER part4_pack_unit_assessment_check_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN NEW.assessment_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM ELIGIBILITY_ASSESSMENT a
    WHERE a.assessment_id = NEW.assessment_id
      AND a.unit_id = NEW.unit_id
      AND a.status = 'final'
      AND a.final_purpose_id BETWEEN 1 AND 9)
BEGIN
    SELECT RAISE(ABORT,
        'BATTERY_PACK_UNIT: assessment must be final, match unit, and support a second-life purpose');
END;

CREATE TRIGGER part4_pack_unit_overlap_unit_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN EXISTS (
    SELECT 1 FROM BATTERY_PACK_UNIT b
    WHERE b.unit_id = NEW.unit_id
      AND NEW.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
      AND COALESCE(NEW.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at)
BEGIN
    SELECT RAISE(ABORT, 'BATTERY_PACK_UNIT: overlapping active installation for the unit');
END;

CREATE TRIGGER part4_pack_unit_overlap_position_insert
BEFORE INSERT ON BATTERY_PACK_UNIT
WHEN EXISTS (
    SELECT 1 FROM BATTERY_PACK_UNIT b
    WHERE b.pack_id = NEW.pack_id
      AND b.position_code = NEW.position_code
      AND NEW.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
      AND COALESCE(NEW.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at)
BEGIN
    SELECT RAISE(ABORT, 'BATTERY_PACK_UNIT: overlapping installation at the same pack position');
END;

CREATE TRIGGER part4_pack_unit_overlap_unit_update
BEFORE UPDATE OF unit_id, pack_id, position_code, joined_at, removed_at
ON BATTERY_PACK_UNIT
WHEN EXISTS (
    SELECT 1 FROM BATTERY_PACK_UNIT b
    WHERE b.unit_id = NEW.unit_id
      AND b.pack_unit_id <> NEW.pack_unit_id
      AND NEW.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
      AND COALESCE(NEW.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at)
BEGIN
    SELECT RAISE(ABORT, 'BATTERY_PACK_UNIT: overlapping active installation for the unit');
END;

CREATE TRIGGER part4_pack_unit_overlap_position_update
BEFORE UPDATE OF unit_id, pack_id, position_code, joined_at, removed_at
ON BATTERY_PACK_UNIT
WHEN EXISTS (
    SELECT 1 FROM BATTERY_PACK_UNIT b
    WHERE b.pack_id = NEW.pack_id
      AND b.position_code = NEW.position_code
      AND b.pack_unit_id <> NEW.pack_unit_id
      AND NEW.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
      AND COALESCE(NEW.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at)
BEGIN
    SELECT RAISE(ABORT, 'BATTERY_PACK_UNIT: overlapping installation at the same pack position');
END;

-- ---------------------------------------------------------------------------
-- 触发器：作业／检查／维护的组一致性与父事件继承
-- ---------------------------------------------------------------------------
CREATE TRIGGER part4_job_maintenance_same_pack_insert
BEFORE INSERT ON ASSEMBLY_JOB
WHEN NEW.maintenance_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM MAINTENANCE_EVENT m
    JOIN lifecycle_event e ON e.event_id = m.maintenance_id
    WHERE m.maintenance_id = NEW.maintenance_id
      AND e.battery_pack_id = NEW.pack_id)
BEGIN
    SELECT RAISE(ABORT, 'ASSEMBLY_JOB: maintenance must target the same pack');
END;

CREATE TRIGGER part4_maintenance_parent_check_insert
BEFORE INSERT ON MAINTENANCE_EVENT
WHEN NOT EXISTS (
    SELECT 1 FROM lifecycle_event e
    WHERE e.event_id = NEW.maintenance_id
      AND e.event_type = 'maintenance'
      AND e.battery_pack_id IS NOT NULL
      AND e.battery_unit_id IS NULL
      AND e.actor_org_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT,
        'MAINTENANCE_EVENT: parent lifecycle event must be pack-targeted maintenance with an actor');
END;

CREATE TRIGGER part4_inspection_trigger_same_pack_insert
BEFORE INSERT ON PACK_INSPECTION
WHEN (NEW.triggered_by_job_code IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM ASSEMBLY_JOB j
          WHERE j.job_code = NEW.triggered_by_job_code AND j.pack_id = NEW.pack_id))
  OR (NEW.triggered_by_maintenance_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM MAINTENANCE_EVENT m
          JOIN lifecycle_event e ON e.event_id = m.maintenance_id
          WHERE m.maintenance_id = NEW.triggered_by_maintenance_id
            AND e.battery_pack_id = NEW.pack_id))
BEGIN
    SELECT RAISE(ABORT, 'PACK_INSPECTION: trigger source must belong to the same pack');
END;

CREATE TRIGGER part4_release_evidence_same_pack_composition_insert
BEFORE INSERT ON SERVICE_RELEASE_INSPECTION
WHEN NOT EXISTS (
    SELECT 1 FROM SERVICE_RELEASE r
    JOIN PACK_INSPECTION i ON i.inspection_code = NEW.inspection_code
    WHERE r.release_code = NEW.release_code
      AND i.pack_id = r.pack_id
      AND i.composition_as_of = r.composition_as_of)
BEGIN
    SELECT RAISE(ABORT,
        'SERVICE_RELEASE_INSPECTION: evidence must be same pack and same composition');
END;

-- ---------------------------------------------------------------------------
-- 触发器：生命周期事件以电池组为目标时必须指向已登记的组
-- （lifecycle_event 由第①板块维护，此触发器只校验第四板块新增记录）
-- ---------------------------------------------------------------------------
CREATE TRIGGER part4_lifecycle_event_pack_target_insert
AFTER INSERT ON lifecycle_event
WHEN NEW.battery_pack_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM BATTERY_PACK p WHERE p.pack_id = NEW.battery_pack_id)
BEGIN
    SELECT RAISE(ABORT, 'lifecycle_event: battery_pack_id must reference BATTERY_PACK');
END;
