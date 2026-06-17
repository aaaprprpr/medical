# 架构说明

## 1. 架构目标

系统采用本地前后端分离架构：

```text
Vue 前端
  -> Spring Boot Java 后端
      -> Python FastAPI 模型服务
      -> 数据库
```

设计目标：

- 前端负责页面、文件夹选择、图像预览和结果展示。
- Java 后端负责对外 API、业务流程、数据保存和模型服务调用。
- Python 服务只负责模型加载和模型推理。
- 模型权重路径和模型内部细节不暴露给前端。

## 2. 当前组件

```text
medical-web/
  Vue + Vite 前端

medical-system/
  Spring Boot Java 后端

python-api/
  FastAPI 模型推理服务

docs/
  项目文档
```

## 3. 调用关系

```text
浏览器
  |
  | multipart/form-data, files[]
  v
Java 后端 /api/predict
  |
  | multipart/form-data, files[]
  v
Python 模型服务 /predict
  |
  | 返回模型结果
  v
Java 后端统一包装响应
  |
  v
Vue 前端展示结果
```

前端上传文件时必须保留相对路径：

```js
formData.append('files', file, relativePath)
```

Java 转发给 Python 时也必须保留该相对路径：

```java
.filename(file.getOriginalFilename())
```

## 4. 服务端口

| 服务 | 地址 |
| --- | --- |
| Vue 前端 | `http://localhost:5173` |
| Java 后端 | `http://localhost:8080` |
| Python 模型服务 | `http://localhost:8000` |
| MySQL 后续预留 | `localhost:3306` |

## 5. Java 后端建议包结构

当前后端还处于早期原型阶段，后续建议整理为：

```text
src/main/java/com/example/medical
  MedicalSystemApplication.java
  common/
    ApiResponse.java
  config/
    RestClientConfig.java
  controller/
    HealthController.java
    PredictController.java
    PatientController.java
    TestRecordController.java
  client/
    ModelServiceClient.java
  service/
    PredictService.java
    PatientService.java
    TestRecordService.java
  dto/
    PredictResponse.java
    PatientRequest.java
    PatientResponse.java
    TestRecordResponse.java
  entity/
    Patient.java
    TestRecord.java
  repository/
    PatientRepository.java
    TestRecordRepository.java
```

## 6. 当前 Java 后端整理建议

当前已有：

```text
controller/HealthController.java
controller/MockPredictController.java
config/RestClientConfig.java
```

建议下一步手动调整：

1. `MockPredictController` 改名为 `PredictController`。
2. 接口路径从 `/api/mock-predict` 逐步调整为 `/api/predict`。
3. 方法名从 `mockPredict` 改为 `predict`。
4. 入参从单文件 `MultipartFile file` 改为多文件 `MultipartFile[] files`。
5. Java 转发 Python 时使用字段名 `files`。
6. 暂时保留统一包装：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

## 7. Python 模型服务设计

Python 服务当前职责：

- `/health` 返回服务状态。
- `/predict` 接收多文件上传。
- 将上传文件临时还原成患者目录。
- 调用 `run_test.py` 中的 `TTSTPredictor`。
- 返回模型推理结果。

Python 服务不负责：

- 保存数据库。
- 管理患者信息。
- 暴露模型权重路径。
- 生成 CSV 报告。

## 8. 数据库接入时机

当前优先级：

1. 先跑通前端 -> Java -> Python 的真实推理闭环。
2. 再整理 Java 后端结构。
3. 再接入数据库。

原因：

- 当前核心风险是多文件路径、模型服务调用和推理结果返回。
- 数据库可以在链路跑通后再接入，避免同时处理太多复杂度。
