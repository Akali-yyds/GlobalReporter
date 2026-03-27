#!/usr/bin/env python3
"""
GlobalReporter 地理数据回填脚本
用于更新现有geo_entities记录，补充新的地理层级字段
"""

import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.geo_entity import GeoEntity
from app.models.event_geo_mapping import EventGeoMapping

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_db_session():
    """创建数据库会话"""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def backfill_geo_entities():
    """回填geo_entities表的新字段"""
    session = create_db_session()
    
    try:
        # 获取所有需要回填的记录
        entities = session.query(GeoEntity).filter(
            GeoEntity.precision_level.is_(None)
        ).all()
        
        logger.info(f"找到 {len(entities)} 条需要回填的geo_entities记录")
        
        updated_count = 0
        
        for entity in entities:
            logger.info(f"处理实体: {entity.name} (geo_key: {entity.geo_key})")
            
            # 基于现有数据推断precision_level和display_mode
            if entity.country_code and len(entity.country_code) == 2:
                # 如果geo_key等于country_code，是国家级
                if entity.geo_key.upper() == entity.country_code.upper():
                    entity.precision_level = 'COUNTRY'
                    entity.display_mode = 'POLYGON'
                    entity.country_name = entity.name
                # 否则可能是城市级
                else:
                    entity.precision_level = 'CITY'  
                    entity.display_mode = 'POINT'
                    entity.city_name = entity.name
            else:
                # 默认设置为CITY级别
                entity.precision_level = 'CITY'
                entity.display_mode = 'POINT' 
                entity.city_name = entity.name
            
            updated_count += 1
            
        # 提交更改
        session.commit()
        logger.info(f"成功回填 {updated_count} 条geo_entities记录")
        
    except Exception as e:
        session.rollback()
        logger.error(f"回填geo_entities时发生错误: {e}")
        raise
    finally:
        session.close()

def backfill_event_geo_mappings():
    """回填event_geo_mappings表的新字段"""
    session = create_db_session()
    
    try:
        # 获取所有需要回填的记录
        mappings = session.query(EventGeoMapping).filter(
            EventGeoMapping.extraction_method.is_(None)
        ).all()
        
        logger.info(f"找到 {len(mappings)} 条需要回填的event_geo_mappings记录")
        
        updated_count = 0
        
        for mapping in mappings:
            # 设置默认值
            mapping.extraction_method = 'legacy'
            mapping.is_primary = False  # 现有数据默认不是主要地区
            mapping.relevance_score = 0.5  # 给一个中等的相关度分数
            
            updated_count += 1
            
        # 提交更改
        session.commit()
        logger.info(f"成功回填 {updated_count} 条event_geo_mappings记录")
        
    except Exception as e:
        session.rollback()
        logger.error(f"回填event_geo_mappings时发生错误: {e}")
        raise
    finally:
        session.close()

def validate_migration():
    """验证迁移结果"""
    session = create_db_session()
    
    try:
        # 检查geo_entities新字段
        logger.info("验证geo_entities表结构...")
        
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(precision_level) as has_precision_level,
                COUNT(display_mode) as has_display_mode,
                COUNT(country_name) as has_country_name
            FROM geo_entities
        """)).fetchone()
        
        logger.info(f"geo_entities验证结果:")
        logger.info(f"  总记录数: {result.total_records}")  
        logger.info(f"  有precision_level: {result.has_precision_level}")
        logger.info(f"  有display_mode: {result.has_display_mode}")
        logger.info(f"  有country_name: {result.has_country_name}")
        
        # 检查precision_level分布
        precision_dist = session.execute(text("""
            SELECT precision_level, COUNT(*) as count 
            FROM geo_entities 
            WHERE precision_level IS NOT NULL 
            GROUP BY precision_level
        """)).fetchall()
        
        logger.info("precision_level分布:")
        for row in precision_dist:
            logger.info(f"  {row.precision_level}: {row.count}")
            
        # 检查event_geo_mappings新字段
        logger.info("验证event_geo_mappings表结构...")
        
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(extraction_method) as has_extraction_method,
                COUNT(CASE WHEN is_primary = true THEN 1 END) as primary_count
            FROM event_geo_mappings
        """)).fetchone()
        
        logger.info(f"event_geo_mappings验证结果:")
        logger.info(f"  总记录数: {result.total_records}")
        logger.info(f"  有extraction_method: {result.has_extraction_method}")  
        logger.info(f"  主要地区数: {result.primary_count}")
        
        # 检查索引
        logger.info("检查新增索引...")
        indexes = session.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename IN ('geo_entities', 'event_geo_mappings') 
                AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """)).fetchall()
        
        logger.info(f"找到 {len(indexes)} 个相关索引:")
        for idx in indexes:
            logger.info(f"  {idx.tablename}.{idx.indexname}")
            
    except Exception as e:
        logger.error(f"验证过程中发生错误: {e}")
        raise
    finally:
        session.close()

def main():
    """主函数"""
    logger.info("开始AiNewser地理数据回填...")
    
    try:
        # 1. 验证当前迁移状态
        validate_migration()
        
        # 2. 回填geo_entities
        backfill_geo_entities()
        
        # 3. 回填event_geo_mappings  
        backfill_event_geo_mappings()
        
        # 4. 最终验证
        logger.info("回填完成，进行最终验证...")
        validate_migration()
        
        logger.info("✅ 地理数据回填成功完成！")
        logger.info("📋 下一步：准备地理词典数据(P2阶段)")
        
    except Exception as e:
        logger.error(f"❌ 回填过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
