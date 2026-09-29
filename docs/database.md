# 数据库

MySQL 8.0.46（本机已有服务），库名 `voice_clone`，字符集 `utf8mb4`。

客户端不在 PATH，完整路径：`D:\ws-soft\MySql\mysql-8.0.46-winx64\bin\mysql.exe`。

## 建表 DDL

```sql
CREATE DATABASE IF NOT EXISTS voice_clone
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE voice_clone;

CREATE TABLE IF NOT EXISTS voices (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name           VARCHAR(100)    NOT NULL,
  description    VARCHAR(500)    NULL,
  ref_audio_path VARCHAR(255)    NOT NULL COMMENT '相对 data/refs 的文件名',
  duration       DECIMAL(6,2)    NULL     COMMENT '参考音频时长（秒）',
  created_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_voices_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS generations (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  voice_id   BIGINT UNSIGNED NULL,
  text       TEXT            NOT NULL,
  audio_path VARCHAR(255)    NOT NULL COMMENT '相对 data/audio 的文件名',
  duration   DECIMAL(6,2)    NULL     COMMENT '生成音频时长（秒）',
  elapsed    DECIMAL(8,2)    NULL     COMMENT '推理耗时（秒）',
  created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_generations_voice_id (voice_id),
  KEY idx_generations_created_at (created_at),
  CONSTRAINT fk_generations_voice
    FOREIGN KEY (voice_id) REFERENCES voices (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 表说明

### voices — 音色

一行代表一个可复用的克隆音色。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键，自增 |
| `name` | VARCHAR(100) | 音色名，必填 |
| `description` | VARCHAR(500) | 描述，可空 |
| `ref_audio_path` | VARCHAR(255) | 参考音频文件名（非完整路径） |
| `duration` | DECIMAL(6,2) | 参考音频时长，秒 |
| `created_at` | TIMESTAMP | 创建时间 |

### generations — 生成历史

一行代表一次合成。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键，自增 |
| `voice_id` | BIGINT UNSIGNED | 外键，可空（音色被删后置空） |
| `text` | TEXT | 合成用的文本 |
| `audio_path` | VARCHAR(255) | 生成音频文件名（非完整路径） |
| `duration` | DECIMAL(6,2) | 生成音频时长，秒 |
| `elapsed` | DECIMAL(8,2) | 推理耗时，秒。`duration / elapsed` 即实时率 |
| `created_at` | TIMESTAMP | 生成时间 |

## 设计说明

**音频文件落磁盘，库里只存文件名。** 完整路径 = 配置的基目录 + 子目录 + 文件名（`web/data/refs/` 或 `web/data/audio/`）。好处是换存储位置不动数据库，且避免把二进制塞进 MySQL。

**`voice_id` 用 `ON DELETE SET NULL` 而非 `CASCADE`。** 删音色时保留历史记录，避免用户误删音色就永久丢失生成历史；前端对 `voice_id` 为 `null` 的条目标注「音色已删除」，音频仍可播放。

**`duration` / `elapsed` 用 `DECIMAL` 而非 `FLOAT`。** 避免浮点显示误差，且这两列只用于展示与观察实时率，不需要浮点运算精度。

**索引。** `created_at` 降序分列索引用于列表分页；`voice_id` 索引用于按音色筛选历史。数据量小，但索引成本低。

## 常用命令

```bash
MYSQL="D:/ws-soft/MySql/mysql-8.0.46-winx64/bin/mysql.exe"

# 连接
"$MYSQL" -uroot -p123456 voice_clone

# 看表
"$MYSQL" -uroot -p123456 -e "SHOW TABLES" voice_clone

# 看音色
"$MYSQL" -uroot -p123456 -e "SELECT id,name,ref_audio_path,duration,created_at FROM voices" voice_clone

# 看生成历史
"$MYSQL" -uroot -p123456 -e "SELECT id,voice_id,LEFT(text,20) AS text,audio_path,elapsed,created_at FROM generations ORDER BY id DESC LIMIT 10" voice_clone
```

## 与 Drizzle 的对应

`web/db/schema.ts` 用 Drizzle ORM 定义这两张表，字段名用 camelCase（`refAudioPath`、`createdAt`），通过 Drizzle 的列映射对应到数据库的 snake_case。表结构以本文档的 DDL 为准，Drizzle 定义不得偏离。
