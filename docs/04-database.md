# 数据库设计

## 1. 当前数据库

数据库类型：MySQL 8.x

数据库名：

```text
medical_system
```

项目账号：

```text
medical_user
```

Spring Boot 通过 `spring.datasource.*` 配置连接 MySQL。

## 2. 设计原则

- 数据库保存业务数据，不保存模型权重。
- 患者基础信息和检测记录分表保存。
- 患者表不直接保存“最近检测结果”。
- “最近检测结果”后续通过 `patients` 和 `test_records` 联表查询得到。
- 第一阶段不保存完整图像二进制，只保存必要的路径或图像名摘要。

## 3. patients 表

用途：保存患者基础信息。

当前已实现。

```sql
CREATE TABLE patients (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    gender VARCHAR(20) NOT NULL,
    age INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT | 主键，自增 |
| name | VARCHAR(100) | 患者姓名或患者文件夹名 |
| gender | VARCHAR(20) | 性别，当前使用 `男` / `女` |
| age | INT | 年龄 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

已实现操作：

- 新增患者。
- 查询患者列表。
- 根据 ID 查询患者。
- 修改患者。
- 删除患者。
- 按姓名关键词搜索。
- 按性别筛选。
- 按字段排序。

## 4. test_records 表

用途：保存每次影像检测结果。

当前尚未实现，下一阶段开发。

建议建表：

```sql
CREATE TABLE test_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    patient_id BIGINT NOT NULL,
    result VARCHAR(50) NOT NULL,
    probability DECIMAL(8, 6) NOT NULL,
    image_name VARCHAR(255),
    patient_folder_name VARCHAR(255),
    tested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_records_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id)
);
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT | 主键，自增 |
| patient_id | BIGINT | 对应患者 ID |
| result | VARCHAR(50) | 模型结果，例如 `mace_cine` / `no_mace` |
| probability | DECIMAL(8,6) | 置信度 |
| image_name | VARCHAR(255) | 最近图像或代表图像名 |
| patient_folder_name | VARCHAR(255) | 上传时识别到的患者文件夹名 |
| tested_at | DATETIME | 检测时间 |

## 5. 后续联表查询目标

患者信息页最终需要展示：

```text
姓名 | 性别 | 年龄 | 最近检测结果 | 最近检测时间 | 最近图像 | 操作
```

这些字段来自两张表：

```text
patients
  基础信息：姓名、性别、年龄

test_records
  最近检测结果、最近检测时间、最近图像
```

后续需要实现类似逻辑：

```sql
SELECT
    p.id,
    p.name,
    p.gender,
    p.age,
    r.result AS latest_result,
    r.probability AS latest_probability,
    r.image_name AS latest_image_name,
    r.tested_at AS latest_test_time
FROM patients p
LEFT JOIN test_records r
    ON r.patient_id = p.id
WHERE r.tested_at = (
    SELECT MAX(r2.tested_at)
    FROM test_records r2
    WHERE r2.patient_id = p.id
);
```

实际实现时需要处理“患者还没有检测记录”的情况，因此会优先使用 `LEFT JOIN`。

## 6. 暂不实现的表

如果后续要记录每一张图像，可以增加 `image_files` 表。当前阶段先不做。

可能字段：

| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| test_record_id | 检测记录 ID |
| modality | `CINE` / `LGE` |
| location_index | Location 编号 |
| frame_index | Frame 编号 |
| relative_path | 上传相对路径 |
| stored_path | 后端保存路径 |
