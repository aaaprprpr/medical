# API 设计

## 1. 基础约定

### 1.1 Java 后端地址

```text
http://localhost:8080
```

### 1.2 Python 模型服务地址

```text
http://localhost:8000
```

### 1.3 Java 后端 API 前缀

```text
/api
```

### 1.4 Java 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

常用错误码暂定：

| code | 说明 |
| --- | --- |
| 0 | 成功 |
| 40000 | 请求参数错误 |
| 40003 | 上传文件为空 |
| 50000 | 系统内部错误 |
| 50001 | 模型服务调用失败 |

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
  "model_loaded": false
}
```

`model_loaded=false` 表示模型还没有被第一次预测请求触发加载。

## 3. 当前检测接口

### 3.1 Java 后端预测接口

当前建议接口：

```http
POST /api/predict
Content-Type: multipart/form-data
```

当前过渡期旧接口：

```http
POST /api/mock-predict
Content-Type: multipart/form-data
```

建议后续删除 `mock` 命名。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| files | file[] | 是 | 患者文件夹下的全部 Cine/LGE 图像 |

文件名必须携带相对路径，例如：

```text
Patient_001/Cine/SA/Location_01/Frame_01.png
Patient_001/LGE/Location_01.png
```

Java 后端响应示例：

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
    "results": [
      {
        "patient_id": "Patient_001",
        "result": "mace_cine",
        "pred_label": 0,
        "probability": 0.8732,
        "prob_mace": 0.8732,
        "prob_no_mace": 0.1268,
        "has_lge": true
      }
    ]
  }
}
```

### 3.2 Python 模型预测接口

该接口只允许 Java 后端调用，前端不直接访问。

```http
POST /predict
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| files | file[] | 是 | 患者文件夹中的全部图像，filename 需要携带相对路径 |

兼容字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| file | file | 旧单文件字段，仅用于临时兼容，不适合真实模型推理 |

响应示例：

```json
{
  "count": 1,
  "patient_id": "Patient_001",
  "result": "mace_cine",
  "pred_label": 0,
  "probability": 0.8732,
  "prob_mace": 0.8732,
  "prob_no_mace": 0.1268,
  "has_lge": true,
  "results": [
    {
      "patient_id": "Patient_001",
      "result": "mace_cine",
      "pred_label": 0,
      "probability": 0.8732,
      "prob_mace": 0.8732,
      "prob_no_mace": 0.1268,
      "has_lge": true
    }
  ]
}
```

## 4. 后续患者接口

数据库接入后实现。

### 4.1 创建患者

```http
POST /api/patients
Content-Type: application/json
```

请求示例：

```json
{
  "name": "Patient_001",
  "gender": "MALE",
  "age": 45
}
```

### 4.2 查询患者列表

```http
GET /api/patients
```

### 4.3 查询患者详情

```http
GET /api/patients/{patientId}
```

## 5. 后续检测记录接口

数据库接入后实现。

### 5.1 创建检测记录并预测

```http
POST /api/patients/{patientId}/tests
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| files | file[] | 是 | 患者影像文件 |
| remark | string | 否 | 备注 |

### 5.2 查询患者检测记录

```http
GET /api/patients/{patientId}/tests
```

### 5.3 查询检测详情

```http
GET /api/tests/{testId}
```
