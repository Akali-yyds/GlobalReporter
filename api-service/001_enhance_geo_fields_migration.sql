-- AiNewser 地理功能升级数据库迁移脚本
-- 执行时间：2026-03-24
-- 说明：为geo_entities和event_geo_mappings表添加多级地理支持字段

-- ===================================================================
-- 第一部分：geo_entities 表结构增强
-- ===================================================================

-- 备份当前数据（可选）
-- CREATE TABLE geo_entities_backup AS SELECT * FROM geo_entities;

-- 1. 添加新的地理层级字段
ALTER TABLE geo_entities ADD COLUMN country_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN admin1_code VARCHAR(10);
ALTER TABLE geo_entities ADD COLUMN admin1_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN admin2_code VARCHAR(10);
ALTER TABLE geo_entities ADD COLUMN admin2_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN city_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN district_name VARCHAR(100);

-- 2. 添加精度和显示模式字段
ALTER TABLE geo_entities ADD COLUMN precision_level VARCHAR(20);
ALTER TABLE geo_entities ADD COLUMN display_mode VARCHAR(20);
ALTER TABLE geo_entities ADD COLUMN geojson_key VARCHAR(100);

-- 3. 添加字段约束
ALTER TABLE geo_entities ADD CONSTRAINT ck_geo_entities_precision_level 
    CHECK (precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2', 'CITY', 'DISTRICT', 'POINT'));

ALTER TABLE geo_entities ADD CONSTRAINT ck_geo_entities_display_mode 
    CHECK (display_mode IN ('POLYGON', 'POINT', 'LIST_ONLY'));

-- 4. 调整坐标字段精度
ALTER TABLE geo_entities ALTER COLUMN lat TYPE DECIMAL(10, 8);
ALTER TABLE geo_entities ALTER COLUMN lng TYPE DECIMAL(11, 8);

-- 5. 数据迁移：将现有 geo_type 映射到新的 precision_level
UPDATE geo_entities SET precision_level = 'COUNTRY' WHERE geo_type = 'country';
UPDATE geo_entities SET precision_level = 'CITY' WHERE geo_type = 'city';
UPDATE geo_entities SET precision_level = 'ADMIN1' WHERE geo_type = 'region';

-- 6. 根据precision_level设置默认display_mode
UPDATE geo_entities SET display_mode = 'POLYGON' 
    WHERE precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2');

UPDATE geo_entities SET display_mode = 'POINT' 
    WHERE precision_level IN ('CITY', 'DISTRICT', 'POINT');

-- 7. 删除旧的geo_type字段
ALTER TABLE geo_entities DROP COLUMN geo_type;

-- ===================================================================
-- 第二部分：event_geo_mappings 表结构增强
-- ===================================================================

-- 备份当前数据（可选）
-- CREATE TABLE event_geo_mappings_backup AS SELECT * FROM event_geo_mappings;

-- 1. 添加地理提取相关字段
ALTER TABLE event_geo_mappings ADD COLUMN matched_text VARCHAR(500);
ALTER TABLE event_geo_mappings ADD COLUMN extraction_method VARCHAR(50);
ALTER TABLE event_geo_mappings ADD COLUMN relevance_score DECIMAL(3, 2);
ALTER TABLE event_geo_mappings ADD COLUMN is_primary BOOLEAN DEFAULT FALSE;
ALTER TABLE event_geo_mappings ADD COLUMN source_text_position VARCHAR(20);

-- 2. 添加字段约束
ALTER TABLE event_geo_mappings ADD CONSTRAINT ck_event_geo_mappings_relevance_score 
    CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0);

ALTER TABLE event_geo_mappings ADD CONSTRAINT ck_event_geo_mappings_source_position 
    CHECK (source_text_position IN ('title', 'summary', 'content'));

-- 3. 调整confidence字段精度
ALTER TABLE event_geo_mappings ALTER COLUMN confidence TYPE DECIMAL(3, 2);

-- 4. 为现有记录设置默认值
UPDATE event_geo_mappings SET is_primary = FALSE WHERE is_primary IS NULL;
UPDATE event_geo_mappings SET extraction_method = 'legacy' WHERE extraction_method IS NULL;

-- 5. 删除废弃字段
ALTER TABLE event_geo_mappings DROP COLUMN geo_type;
ALTER TABLE event_geo_mappings DROP COLUMN display_type;

-- ===================================================================
-- 第三部分：创建优化索引
-- ===================================================================

-- geo_entities 索引
CREATE INDEX idx_geo_entities_precision_level ON geo_entities(precision_level);
CREATE INDEX idx_geo_entities_display_mode ON geo_entities(display_mode);
CREATE INDEX idx_geo_entities_country_admin1 ON geo_entities(country_code, admin1_code);
CREATE INDEX idx_geo_entities_coords ON geo_entities(lat, lng) WHERE lat IS NOT NULL AND lng IS NOT NULL;
CREATE INDEX idx_geo_entities_geojson_key ON geo_entities(geojson_key) WHERE geojson_key IS NOT NULL;

-- event_geo_mappings 索引
CREATE INDEX idx_event_geo_mappings_extraction_method ON event_geo_mappings(extraction_method);
CREATE INDEX idx_event_geo_mappings_is_primary ON event_geo_mappings(is_primary) WHERE is_primary = TRUE;
CREATE INDEX idx_event_geo_mappings_confidence ON event_geo_mappings(confidence DESC);
CREATE INDEX idx_event_geo_mappings_relevance_score ON event_geo_mappings(relevance_score DESC);

-- ===================================================================
-- 第四部分：验证脚本
-- ===================================================================

-- 验证geo_entities表结构
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default 
FROM information_schema.columns 
WHERE table_name = 'geo_entities' 
    AND column_name IN ('country_name', 'admin1_code', 'admin1_name', 'precision_level', 'display_mode')
ORDER BY ordinal_position;

-- 验证event_geo_mappings表结构
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default 
FROM information_schema.columns 
WHERE table_name = 'event_geo_mappings' 
    AND column_name IN ('matched_text', 'extraction_method', 'relevance_score', 'is_primary')
ORDER BY ordinal_position;

-- 验证数据迁移结果
SELECT 
    precision_level, 
    display_mode, 
    COUNT(*) as count 
FROM geo_entities 
GROUP BY precision_level, display_mode;

-- 验证索引创建
SELECT 
    indexname, 
    tablename, 
    indexdef 
FROM pg_indexes 
WHERE tablename IN ('geo_entities', 'event_geo_mappings') 
    AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- ===================================================================
-- 执行完成提示
-- ===================================================================

-- 执行完成后，输出确认信息
DO $$
BEGIN
    RAISE NOTICE '===============================================';
    RAISE NOTICE 'AiNewser 地理功能升级迁移完成！';
    RAISE NOTICE '时间: %', NOW();
    RAISE NOTICE '===============================================';
    RAISE NOTICE '新增字段概览：';
    RAISE NOTICE '- geo_entities: country_name, admin1_code/name, precision_level, display_mode 等';
    RAISE NOTICE '- event_geo_mappings: matched_text, confidence, is_primary 等';
    RAISE NOTICE '===============================================';
    RAISE NOTICE '下一步：执行地理词典准备和数据回填';
    RAISE NOTICE '===============================================';
END $$;
