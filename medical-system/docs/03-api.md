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

### 1.4 统一响应格式

成功：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

失败：

```json
{
  "code": 40001,
  "message": "患者不存在",
  "data": null
}
```

### 1.5 常用错误码

| code | 说明 |
| --- | --- |
| 0 | 成功 |
| 40000 | 请求参数错误 |
| 40001 | 患者不存在 |
| 40002 | 检测记录不存在 |
| 40003 | 文件不能为空 |
| 50000 | 系统内部错误 |
| 50001 | 模型服务调用失败 |

## 2. 系统接口

### 2.1 健康检查

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

## 3. 患者接口

### 3.1 创建患者

```http
POST /api/patients
Content-Type: application/json
```

请求体：

```json
{
  "name": "张三",
  "gender": "MALE",
  "age": 45
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| name | string | 是 | 患者姓名 |
| gender | string | 否 | 性别，`MALE` 或 `FEMALE` |
| age | integer | 否 | 年龄 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "张三",
    "gender": "MALE",
    "age": 45,
    "createdAt": "2026-06-13T20:00:00"
  }
}
```

### 3.2 查询患者列表

```http
GET /api/patients?page=1&size=10&keyword=张
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | integer | 否 | 页码，从 1 开始 |
| size | integer | 否 | 每页数量 |
| keyword | string | 否 | 按姓名模糊查询 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 1,
    "items": [
      {
        "id": 1,
        "name": "张三",
        "gender": "MALE",
        "age": 45,
        "createdAt": "2026-06-13T20:00:00"
      }
    ]
  }
}
```

### 3.3 查询患者详情

```http
GET /api/patients/{patientId}
```

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| patientId | long | 患者 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "张三",
    "gender": "MALE",
    "age": 45,
    "createdAt": "2026-06-13T20:00:00"
  }
}
```

## 4. 检测接口

### 4.1 上传影像并检测

```http
POST /api/patients/{patientId}/tests
Content-Type: multipart/form-data
```

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| patientId | long | 患者 ID |

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 医学影像文件 |
| remark | string | 否 | 检测备注 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1001,
    "patientId": 1,
    "imagePath": "uploads/2026/06/13/a001.png",
    "result": "POSITIVE",
    "probability": 0.8732,
    "remark": "首次检测",
    "createdAt": "2026-06-13T20:10:00"
  }
}
```

### 4.2 查询患者检测记录

```http
GET /api/patients/{patientId}/tests
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1001,
      "patientId": 1,
      "imagePath": "uploads/2026/06/13/a001.png",
      "result": "POSITIVE",
      "probability": 0.8732,
      "remark": "首次检测",
      "createdAt": "2026-06-13T20:10:00"
    }
  ]
}
```

### 4.3 查询检测详情

```http
GET /api/tests/{testId}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1001,
    "patientId": 1,
    "imagePath": "uploads/2026/06/13/a001.png",
    "result": "POSITIVE",
    "probability": 0.8732,
    "remark": "首次检测",
    "createdAt": "2026-06-13T20:10:00"
  }
}
```

## 5. Python 模型服务接口

该接口由 Java 后端调用，前端不直接访问。

### 5.1 模型预测

```http
POST /predict
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 医学影像文件 |

响应示例：

```json
{
  "result": "POSITIVE",
  "probability": 0.8732
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| result | string | `POSITIVE` 或 `NEGATIVE` |
| probability | number | 阳性概率，范围 0 到 1 |

