# 开发计划

## 1. 开发原则

- 先跑通最小闭环，再逐步整理结构。
- 文档要跟随当前真实进度更新。
- 当前项目是学习型原型，允许先实现，再回头整理命名和层次。
- 每次改接口时，同时更新 API 文档。

## 2. 当前已完成

### 前端

- Vue + Vite 项目已创建。
- 已实现顶部菜单。
- 已实现影像检测页面左右布局。
- 已实现患者文件夹选择。
- 已实现 Cine/LGE 图像解析。
- 已实现 Cine Location 切换。
- 已实现缩略图相册。
- 已实现单图查看器、上一张、下一张、关闭。
- 前端提交逻辑已开始从单文件改为多文件 `files`。

### Python 模型服务

- FastAPI 服务已创建。
- `/health` 可用。
- `run_test.py` 已能读取前端格式的本地患者目录。
- `run_test.py` 已抽出可复用 `TTSTPredictor`。
- 模型权重路径保留在服务端配置中，不暴露给前端。
- `/predict` 已准备接收多文件并还原临时患者目录。

### Java 后端

- Spring Boot 项目已创建。
- `GET /api/health` 可用。
- 已实现早期 `MockPredictController` 单文件中转接口。
- 当前 Java 后端还未完成多文件上传和相对路径转发。

## 3. 当前最近任务

### T1：前端多文件提交

目标：

- 前端将 `cineImages + lgeImages` 全部作为 `files` 上传。
- `FormData.append` 第三个参数使用图像相对路径。

状态：

- 已开始调整。

### T2：Java 后端多文件接收与转发

目标：

- `MockPredictController` 改为正式预测控制器。
- 接收 `MultipartFile[] files`。
- 循环转发到 Python `/predict`。
- 转发时保留 `file.getOriginalFilename()`。

建议手动改动：

```text
MockPredictController.java
  -> PredictController.java

/api/mock-predict
  -> /api/predict

@RequestPart("file") MultipartFile file
  -> @RequestPart("files") MultipartFile[] files
```

### T3：前后端接口路径统一

目标：

- 前端从 `/api/mock-predict` 改为 `/api/predict`。
- Java 后端正式提供 `/api/predict`。
- 旧 mock 命名删除。

### T4：真实推理链路验证

目标：

```text
Vue 选择患者文件夹
 -> Java 接收多文件
 -> Java 转发 Python
 -> Python 真实模型推理
 -> Java 包装响应
 -> Vue 展示结果
```

## 4. 后端整理计划


### 阶段 B2：拆分模型服务调用

新增：

```text
client/ModelServiceClient.java
service/PredictService.java
dto/PredictResponse.java
```

职责：

- `PredictController` 只处理 HTTP 请求。
- `PredictService` 处理预测业务编排。
- `ModelServiceClient` 专门调用 Python 服务。

### 阶段 B3：统一响应对象

新增：

```text
common/ApiResponse.java
```

减少每个接口手写：

```java
Map.of("code", 0, "message", "success", "data", data)
```

### 阶段 B4：接入数据库

- 建立 `patient` 表。
- 建立 `test_record` 表。
- 保存检测记录。
- 支持历史记录查询。

## 5. 暂不处理

- 用户登录注册。
- 权限控制。
- 正式医疗报告。
- 云部署。
- 多模型管理。
- 医疗合规。

这些可以后续作为练习模块逐步加入。
