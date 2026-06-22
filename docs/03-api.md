# API 文档

## 1. 基础约定

Java 后端地址：

```text
http://localhost:8080
```

Python 模型服务地址：

```text
http://localhost:8000
```

Java 后端统一响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

## 2. 健康检查

### 2.1 Java 后端健康检查

```http
GET /api/health
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "UP"
  }
}
```

### 2.2 Python 模型服务健康检查

```http
GET /health
```

响应示例：

```json
{
  "status": "UP",
  "model_loaded": true
}
```

## 3. 影像预测接口

### 3.1 Java 后端预测接口

前端调用该接口。

```http
POST /api/predict
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| files | file[] | 是 | 患者文件夹下解析出的全部 Cine/LGE 图像 |

文件名必须携带相对路径，例如：

```text
Patient_001/Cine/SA/Location_01/Frame_01.png
Patient_001/LGE/Location_01.png
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 1,
    "patient_id": "Patient_001",
    "result": "mace_cine",
    "pred_label": 0,
    "probability": 0.8732,
    "prob_mace": 0.8732,
    "prob_no_mace": 0.1268,
    "has_lge": true,
    "results": []
  }
}
```

### 3.2 Python 模型预测接口

只允许 Java 后端调用，前端不直接访问。

```http
POST /predict
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| files | file[] | 是 | 患者文件夹中的全部图像，filename 需要携带相对路径 |

## 4. 患者接口

### 4.1 查询患者列表

```http
GET /api/patients
```

支持查询参数：

| 参数 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| keyword | 否 | `001` | 按姓名模糊搜索 |
| gender | 否 | `男` | 按性别筛选 |
| sortBy | 否 | `age` | 排序字段 |
| order | 否 | `asc` | 排序方向，`asc` 或 `desc` |

支持的 `sortBy`：

| 前端参数 | 数据库字段 |
| --- | --- |
| `id` | `id` |
| `name` | `name` |
| `gender` | `gender` |
| `age` | `age` |
| `createdAt` | `created_at` |
| `updatedAt` | `updated_at` |

请求示例：

```http
GET /api/patients?keyword=Patient&gender=男&sortBy=age&order=desc
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "Patient_001",
      "gender": "男",
      "age": 45,
      "createdAt": "2026-06-19T11:51:33",
      "updatedAt": "2026-06-19T11:51:33"
    }
  ]
}
```

### 4.2 查询单个患者

```http
GET /api/patients/{id}
```

示例：

```http
GET /api/patients/1
```

### 4.3 新增患者

```http
POST /api/patients
Content-Type: application/json
```

请求示例：

```json
{
  "name": "Patient_003",
  "gender": "男",
  "age": 52
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "affectedRows": 1
  }
}
```

### 4.4 修改患者

```http
PUT /api/patients/{id}
Content-Type: application/json
```

请求示例：

```json
{
  "name": "Patient_003",
  "gender": "男",
  "age": 53
}
```

### 4.5 删除患者

```http
DELETE /api/patients/{id}
```

该接口当前执行物理删除。

## 5. 检测记录接口

检测记录接口尚未实现，后续预计包括：

```http
GET /api/patients/{patientId}/records
GET /api/records/{recordId}
POST /api/patients/{patientId}/records
```

后续患者列表中的“最近检测结果”应由患者表和检测记录表联表查询得到。
