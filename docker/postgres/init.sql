-- AgentHub 数据库初始化：启用 pgvector 扩展
-- 表结构由 Alembic 迁移管理，此处仅启用扩展。
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
