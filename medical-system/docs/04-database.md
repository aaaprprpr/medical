# 数据库设计

## 1. 设计目标

数据库用于保存患者基础信息和检测记录。第一阶段保持表结构简单，优先支撑核心业务闭环。

## 2. 表关系

```text
patient 1 ---- N test_record
```

一个患者可以有多条检测记录，一条检测记录只属于一个患者。

## 3. 表清单

| 表名 | 说明 |
| --- | --- |
| patient | 患者表 |
| test_record | 检测记录表 |

## 4. patient 表

### 4.1 字段设计

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | 主键，自增 | 患者 ID |
| name | VARCHAR(64) | 非空 | 患者姓名 |
| gender | VARCHAR(16) | 可空 | 性别，`MALE` 或 `FEMALE` |
| age | INT | 可空 | 年龄 |
| created_at | DATETIME | 非空 | 创建时间 |
| updated_at | DATETIME | 可空 | 更新时间 |

### 4.2 建表示例

```sql
CREATE TABLE patient (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  gender VARCHAR(16),
  age INT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME
);
```

## 5. test_record 表

### 5.1 字段设计

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | 主键，自增 | 检测记录 ID |
| patient_id | BIGINT | 非空，外键 | 患者 ID |
| image_path | VARCHAR(255) | 非空 | 影像文件保存路径 |
| result | VARCHAR(16) | 非空 | 检测结果，`POSITIVE` 或 `NEGATIVE` |
| probability | DECIMAL(8,6) | 可空 | 阳性概率 |
| remark | VARCHAR(255) | 可空 | 备注 |
| created_at | DATETIME | 非空 | 检测时间 |

### 5.2 建表示例

```sql
CREATE TABLE test_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  patient_id BIGINT NOT NULL,
  image_path VARCHAR(255) NOT NULL,
  result VARCHAR(16) NOT NULL,
  probability DECIMAL(8,6),
  remark VARCHAR(255),
  created_at DATETIME NOT NULL,
  CONSTRAINT fk_test_record_patient
    FOREIGN KEY (patient_id) REFERENCES patient(id)
);
```

## 6. 索引设计

```sql
CREATE INDEX idx_patient_name ON patient(name);
CREATE INDEX idx_test_record_patient_id ON test_record(patient_id);
CREATE INDEX idx_test_record_created_at ON test_record(created_at);
```

## 7. 初始样例数据

```sql
INSERT INTO patient (name, gender, age, created_at)
VALUES ('张三', 'MALE', 45, NOW());
```

## 8. 后续扩展字段

后续如果需要增强真实业务感，可以考虑增加：

- 患者编号。
- 手机号。
- 出生日期。
- 检测状态，例如 `PENDING`、`SUCCESS`、`FAILED`。
- 模型版本。
- 原始文件名。
- 错误信息。

第一阶段不建议提前加入过多字段，避免影响主流程实现。

