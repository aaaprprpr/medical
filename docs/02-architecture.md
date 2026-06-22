# 架构说明

## 1. 总体架构

系统采用本地前后端分离结构：

```text
浏览器
  |
  v
Vue 前端 medical-web
  |
  | HTTP
  v
Spring Boot 后端 medical-system
  |                 |
  | HTTP            | JDBC
  v                 v
Python FastAPI      MySQL
python-api          medical_system
```

职责划分：

| 模块 | 职责 |
| --- | --- |
| Vue 前端 | 页面展示、文件夹选择、图像预览、收集搜索条件、调用 Java 后端 |
| Java 后端 | 对外 API、业务流程编排、数据库访问、调用 Python 模型服务 |
| Python 服务 | 加载模型、执行推理、返回预测结果 |
| MySQL | 保存患者信息和后续检测记录 |

## 2. 服务端口

| 服务 | 地址 |
| --- | --- |
| Vue 前端 | `http://localhost:5173` |
| Java 后端 | `http://localhost:8080` |
| Python 模型服务 | `http://localhost:8000` |
| MySQL | `localhost:3306` |

## 3. 影像检测调用链路

```text
用户选择患者文件夹
  -> Vue 解析 Cine/LGE 文件
  -> Vue 使用 multipart/form-data 上传 files
  -> Java /api/predict 接收 MultipartFile[]
  -> Java 保留 originalFilename 转发给 Python /predict
  -> Python 临时还原患者目录
  -> Python 调用模型推理
  -> Python 返回预测结果
  -> Java 统一包装响应
  -> Vue 展示结果
```

前端上传时必须保留相对路径：

```js
formData.append('files', file, relativePath)
```

Java 转发给 Python 时也必须保留文件名：

```java
.filename(file.getOriginalFilename())
```

## 4. 患者信息调用链路

```text
Vue 患者信息页
  -> GET /api/patients
  -> Java PatientController
  -> PatientRepository
  -> MySQL patients
  -> 返回患者列表
```

新增、修改、删除同理：

```text
Vue 表单操作
  -> POST/PUT/DELETE /api/patients
  -> Java 后端执行 SQL
  -> MySQL 更新数据
  -> Vue 刷新表格
```

## 5. Java 后端当前结构

```text
medical-system/src/main/java/com/example/medical
  MedicalSystemApplication.java
  config/
    RestClientConfig.java
  controller/
    HealthController.java
    PredictController.java
    PatientController.java
    DatabaseController.java
  dto/
    CreatePatientRequest.java
    UpdatePatientRequest.java
  model/
    Patient.java
  repository/
    PatientRepository.java
```

说明：

- `controller` 接收 HTTP 请求。
- `dto` 承接请求体或响应数据。
- `model` 表示业务数据对象。
- `repository` 负责 SQL 和数据库访问。
- `config` 放 Spring 配置类。

## 6. 后端后续建议结构

当前为了学习 SQL，患者功能先直接使用 `Controller -> Repository`。后续代码变复杂后，再拆出 `Service` 层：

```text
controller/
  PatientController.java
service/
  PatientService.java
repository/
  PatientRepository.java
```

拆分后职责：

- `Controller` 只处理 HTTP 入参和响应。
- `Service` 处理业务规则。
- `Repository` 只处理 SQL。

## 7. Python 服务职责边界

Python 服务负责：

- `/health` 健康检查。
- `/predict` 接收多文件。
- 临时还原患者目录。
- 调用模型推理。
- 返回模型结果。

Python 服务不负责：

- 管理患者信息。
- 访问 MySQL。
- 保存检测记录。
- 暴露模型权重路径给前端。
