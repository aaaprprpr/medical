# 数据库设计

当前阶段暂未接入数据库。数据库设计先作为后续实现依据。

## 1. 设计目标

数据库只保存业务数据和文件路径，不保存模型权重，不保存完整图像二进制。

当前计划保存：

- 患者信息。
- 检测记录。
- 检测结果。
- 上传文件根目录或相对路径摘要。

## 2. patient 表

患者基础信息表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint | 主键 |
| name | varchar | 患者姓名或患者文件夹名 |
| gender | varchar | `MALE` / `FEMALE` |
| age | int | 年龄 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3. test_record 表

检测记录表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint | 主键 |
| patient_id | bigint | 患者 ID |
| patient_folder_name | varchar | 上传时识别到的患者文件夹名 |
| image_root_path | varchar | Java 后端保存文件的根目录 |
| result | varchar | 模型预测类别 |
| pred_label | int | 模型预测标签 |
| probability | decimal | 最高类别概率 |
| prob_mace | decimal | MACE 概率 |
| prob_no_mace | decimal | no_mace 概率 |
| has_lge | boolean | 是否包含 LGE 图像 |
| created_at | datetime | 检测时间 |

## 4. 可选 image_file 表

如果后续需要记录每张图像，可以增加该表。当前阶段不强制实现。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint | 主键 |
| test_record_id | bigint | 检测记录 ID |
| modality | varchar | `CINE` / `LGE` |
| location_index | int | Location 编号 |
| frame_index | int | Frame 编号，LGE 可为空 |
| relative_path | varchar | 上传相对路径 |
| stored_path | varchar | 后端保存路径 |

## 5. 当前实现顺序建议

1. 先只实现 `patient` 和 `test_record`。
2. 不急着实现 `image_file`。
3. Java 后端先保存上传根目录和模型结果。
4. 历史记录页面先从 `test_record` 查询。
