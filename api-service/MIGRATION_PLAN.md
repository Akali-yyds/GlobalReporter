# AiNewser 地理功能升级 - 数据库迁移方案

## 迁移概述

基于P0阶段建模决策，对现有geo_entities和event_geo_mappings表进行字段增强。

## 当前表结构分析

### geo_entities (现有)
```sql
CREATE TABLE geo_entities (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    geo_key VARCHAR(20) NOT NULL UNIQUE,
    geo_type VARCHAR(20) NOT NULL,  -- 需要替换为precision_level
    country_code VARCHAR(10) NOT NULL,
    lat FLOAT,
    lng FLOAT,
    is_active BOOLEAN DEFAULT TRUE
);
```

### event_geo_mappings (现有)
```sql
CREATE TABLE event_geo_mappings (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_id VARCHAR(36) NOT NULL,
    geo_id VARCHAR(36) NOT NULL,
    geo_key VARCHAR(20) NOT NULL,
    geo_type VARCHAR(20) NOT NULL,  -- 需要移除
    display_type VARCHAR(20) DEFAULT 'point',  -- 需要替换
    confidence FLOAT DEFAULT 1.0
);
```

## 迁移策略

### 第一步：增强geo_entities表
```sql
-- 新增地理层级字段
ALTER TABLE geo_entities ADD COLUMN country_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN admin1_code VARCHAR(10);  
ALTER TABLE geo_entities ADD COLUMN admin1_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN admin2_code VARCHAR(10);
ALTER TABLE geo_entities ADD COLUMN admin2_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN city_name VARCHAR(100);
ALTER TABLE geo_entities ADD COLUMN district_name VARCHAR(100);

-- 新增精度和显示字段
ALTER TABLE geo_entities ADD COLUMN precision_level VARCHAR(20) CHECK (precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2', 'CITY', 'DISTRICT', 'POINT'));
ALTER TABLE geo_entities ADD COLUMN display_mode VARCHAR(20) CHECK (display_mode IN ('POLYGON', 'POINT', 'LIST_ONLY'));
ALTER TABLE geo_entities ADD COLUMN geojson_key VARCHAR(100);

-- 调整坐标精度
ALTER TABLE geo_entities ALTER COLUMN lat TYPE DECIMAL(10, 8);
ALTER TABLE geo_entities ALTER COLUMN lng TYPE DECIMAL(11, 8);

-- 数据迁移：将geo_type映射到precision_level
UPDATE geo_entities SET precision_level = 'COUNTRY' WHERE geo_type = 'country';
UPDATE geo_entities SET precision_level = 'CITY' WHERE geo_type = 'city';
UPDATE geo_entities SET precision_level = 'ADMIN1' WHERE geo_type = 'region';

-- 设置默认display_mode
UPDATE geo_entities SET display_mode = 'POLYGON' WHERE precision_level IN ('COUNTRY', 'ADMIN1');
UPDATE geo_entities SET display_mode = 'POINT' WHERE precision_level IN ('CITY', 'DISTRICT');

-- 删除旧字段
ALTER TABLE geo_entities DROP COLUMN geo_type;
```

### 第二步：增强event_geo_mappings表
```sql
-- 新增提取相关字段
ALTER TABLE event_geo_mappings ADD COLUMN matched_text VARCHAR(500);
ALTER TABLE event_geo_mappings ADD COLUMN extraction_method VARCHAR(50);
ALTER TABLE event_geo_mappings ADD COLUMN relevance_score DECIMAL(3, 2) CHECK (relevance_score >= 0 AND relevance_score <= 1);
ALTER TABLE event_geo_mappings ADD COLUMN is_primary BOOLEAN DEFAULT FALSE;
ALTER TABLE event_geo_mappings ADD COLUMN source_text_position VARCHAR(20) CHECK (source_text_position IN ('title', 'summary', 'content'));

-- 调整confidence字段精度
ALTER TABLE event_geo_mappings ALTER COLUMN confidence TYPE DECIMAL(3, 2);

-- 删除废弃字段
ALTER TABLE event_geo_mappings DROP COLUMN geo_type;
ALTER TABLE event_geo_mappings DROP COLUMN display_type;
```

### 第三步：创建索引
```sql
-- geo_entities索引优化
CREATE INDEX idx_geo_entities_precision ON geo_entities(precision_level);
CREATE INDEX idx_geo_entities_display ON geo_entities(display_mode);
CREATE INDEX idx_geo_entities_country_admin1 ON geo_entities(country_code, admin1_code);
CREATE INDEX idx_geo_entities_coords ON geo_entities(lat, lng) WHERE lat IS NOT NULL AND lng IS NOT NULL;
CREATE INDEX idx_geo_entities_geojson ON geo_entities(geojson_key) WHERE geojson_key IS NOT NULL;

-- event_geo_mappings索引优化  
CREATE INDEX idx_event_geo_extraction ON event_geo_mappings(extraction_method);
CREATE INDEX idx_event_geo_primary ON event_geo_mappings(is_primary) WHERE is_primary = TRUE;
CREATE INDEX idx_event_geo_confidence ON event_geo_mappings(confidence DESC);
CREATE INDEX idx_event_geo_relevance ON event_geo_mappings(relevance_score DESC);
```

## 迁移文件结构

### 001_enhance_geo_fields.py
```python
"""Enhance geo fields for multi-level geographic support

Revision ID: 001_enhance_geo_fields  
Revises: 
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_enhance_geo_fields'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # geo_entities增强
    op.add_column('geo_entities', sa.Column('country_name', sa.String(100)))
    op.add_column('geo_entities', sa.Column('admin1_code', sa.String(10)))
    op.add_column('geo_entities', sa.Column('admin1_name', sa.String(100)))
    op.add_column('geo_entities', sa.Column('admin2_code', sa.String(10)))
    op.add_column('geo_entities', sa.Column('admin2_name', sa.String(100)))
    op.add_column('geo_entities', sa.Column('city_name', sa.String(100)))
    op.add_column('geo_entities', sa.Column('district_name', sa.String(100)))
    
    # 添加枚举字段
    op.add_column('geo_entities', sa.Column('precision_level', 
        sa.String(20), 
        sa.CheckConstraint("precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2', 'CITY', 'DISTRICT', 'POINT')")
    ))
    op.add_column('geo_entities', sa.Column('display_mode', 
        sa.String(20),
        sa.CheckConstraint("display_mode IN ('POLYGON', 'POINT', 'LIST_ONLY')")
    ))
    op.add_column('geo_entities', sa.Column('geojson_key', sa.String(100)))
    
    # 调整坐标精度
    op.alter_column('geo_entities', 'lat', type_=sa.DECIMAL(10, 8))
    op.alter_column('geo_entities', 'lng', type_=sa.DECIMAL(11, 8))
    
    # 数据迁移
    op.execute("UPDATE geo_entities SET precision_level = 'COUNTRY' WHERE geo_type = 'country'")
    op.execute("UPDATE geo_entities SET precision_level = 'CITY' WHERE geo_type = 'city'") 
    op.execute("UPDATE geo_entities SET precision_level = 'ADMIN1' WHERE geo_type = 'region'")
    op.execute("UPDATE geo_entities SET display_mode = 'POLYGON' WHERE precision_level IN ('COUNTRY', 'ADMIN1')")
    op.execute("UPDATE geo_entities SET display_mode = 'POINT' WHERE precision_level IN ('CITY', 'DISTRICT')")
    
    # 删除旧字段
    op.drop_column('geo_entities', 'geo_type')
    
    # event_geo_mappings增强
    op.add_column('event_geo_mappings', sa.Column('matched_text', sa.String(500)))
    op.add_column('event_geo_mappings', sa.Column('extraction_method', sa.String(50)))
    op.add_column('event_geo_mappings', sa.Column('relevance_score', 
        sa.DECIMAL(3, 2),
        sa.CheckConstraint("relevance_score >= 0 AND relevance_score <= 1")
    ))
    op.add_column('event_geo_mappings', sa.Column('is_primary', sa.Boolean, default=False))
    op.add_column('event_geo_mappings', sa.Column('source_text_position', 
        sa.String(20),
        sa.CheckConstraint("source_text_position IN ('title', 'summary', 'content')")
    ))
    
    # 调整confidence精度
    op.alter_column('event_geo_mappings', 'confidence', type_=sa.DECIMAL(3, 2))
    
    # 删除废弃字段
    op.drop_column('event_geo_mappings', 'geo_type')
    op.drop_column('event_geo_mappings', 'display_type')
    
    # 创建索引
    op.create_index('idx_geo_entities_precision', 'geo_entities', ['precision_level'])
    op.create_index('idx_geo_entities_display', 'geo_entities', ['display_mode'])
    op.create_index('idx_geo_entities_country_admin1', 'geo_entities', ['country_code', 'admin1_code'])
    op.create_index('idx_geo_entities_coords', 'geo_entities', ['lat', 'lng'])
    op.create_index('idx_geo_entities_geojson', 'geo_entities', ['geojson_key'])
    
    op.create_index('idx_event_geo_extraction', 'event_geo_mappings', ['extraction_method'])
    op.create_index('idx_event_geo_primary', 'event_geo_mappings', ['is_primary'])
    op.create_index('idx_event_geo_confidence', 'event_geo_mappings', ['confidence'])
    op.create_index('idx_event_geo_relevance', 'event_geo_mappings', ['relevance_score'])

def downgrade():
    # 回滚操作
    op.drop_index('idx_event_geo_relevance')
    op.drop_index('idx_event_geo_confidence') 
    op.drop_index('idx_event_geo_primary')
    op.drop_index('idx_event_geo_extraction')
    op.drop_index('idx_geo_entities_geojson')
    op.drop_index('idx_geo_entities_coords')
    op.drop_index('idx_geo_entities_country_admin1')
    op.drop_index('idx_geo_entities_display')
    op.drop_index('idx_geo_entities_precision')
    
    # 恢复旧字段
    op.add_column('event_geo_mappings', sa.Column('geo_type', sa.String(20)))
    op.add_column('event_geo_mappings', sa.Column('display_type', sa.String(20), default='point'))
    op.add_column('geo_entities', sa.Column('geo_type', sa.String(20)))
    
    # 删除新字段
    op.drop_column('event_geo_mappings', 'source_text_position')
    op.drop_column('event_geo_mappings', 'is_primary')
    op.drop_column('event_geo_mappings', 'relevance_score')
    op.drop_column('event_geo_mappings', 'extraction_method')
    op.drop_column('event_geo_mappings', 'matched_text')
    
    op.drop_column('geo_entities', 'geojson_key')
    op.drop_column('geo_entities', 'display_mode')
    op.drop_column('geo_entities', 'precision_level')
    op.drop_column('geo_entities', 'district_name')
    op.drop_column('geo_entities', 'city_name')
    op.drop_column('geo_entities', 'admin2_name')
    op.drop_column('geo_entities', 'admin2_code')
    op.drop_column('geo_entities', 'admin1_name')
    op.drop_column('geo_entities', 'admin1_code')
    op.drop_column('geo_entities', 'country_name')
```

## 迁移前检查清单

- [ ] 备份生产数据库
- [ ] 在测试环境验证迁移脚本
- [ ] 确认现有数据的geo_type分布情况
- [ ] 准备回滚预案
- [ ] 确认应用停机时间窗口

## 迁移后验证

- [ ] 验证所有新字段创建成功
- [ ] 验证数据迁移完整性（geo_type -> precision_level）
- [ ] 验证索引创建成功
- [ ] 测试基础查询性能
- [ ] 验证应用启动正常
