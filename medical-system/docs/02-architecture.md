# 架构说明

## 1. 架构目标

系统采用前后端分离和模型服务分离的本地开发架构。目标是让前端、Java 后端、数据库、Python 模型服务各自职责清晰，便于学习工程化开发流程。

## 2. 总体架构

```text
Vue Frontend
http://localhost:5173
        |
        | REST API
        v
Spring Boot Backend
http://localhost:8080
        |
        | JDBC / JPA
        v
Database
H2 or MySQL
        ^
        |
        | HTTP multipart request
        v
Python Model Service
http://localhost:8000
```

## 3. 组件职责

### 3.1 Vue 前端

- 提供患者列表、患者录入、患者详情、影像上传和检测结果展示页面。
- 调用 Java 后端 API。
- 不直接调用 Python 模型服务。
- 不直接操作数据库。

### 3.2 Spring Boot 后端

- 对前端提供 REST API。
- 处理患者和检测记录业务逻辑。
- 接收影像文件上传。
- 保存文件到本地目录。
- 调用 Python 模型服务。
- 保存检测结果到数据库。

### 3.3 数据库

- 保存患者信息。
- 保存检测记录。
- 不保存模型权重。
- 初期可使用 H2 简化配置，后续切换 MySQL。

### 3.4 Python 模型服务

- 封装医学影像二分类模型。
- 对 Java 后端提供 `/predict` 接口。
- 接收影像文件。
- 返回二分类结果和置信度。

## 4. 端口规划

| 服务 | 端口 | 地址 |
| --- | --- | --- |
| Vue 前端 | 5173 | `http://localhost:5173` |
| Spring Boot 后端 | 8080 | `http://localhost:8080` |
| Python 模型服务 | 8000 | `http://localhost:8000` |
| MySQL | 3306 | `localhost:3306` |

## 5. 后端分层

```text
controller
接收 HTTP 请求，进行参数绑定，返回响应。

service
处理业务逻辑，例如创建患者、发起检测、保存检测记录。

repository
访问数据库。

entity
数据库表对应的 Java 实体。

dto
接口请求和响应对象。

client
调用外部服务，例如 Python 模型服务。
```

建议目录结构：

```text
src/main/java/com/example/medical
  MedicalSystemApplication.java
  controller/
  service/
  repository/
  entity/
  dto/
  client/
  config/
  common/
```

## 6. 数据流

### 6.1 创建患者

```text
前端表单
 -> POST /api/patients
 -> 后端校验参数
 -> 写入 patient 表
 -> 返回患者信息
```

### 6.2 上传影像并检测

```text
前端选择文件
 -> POST /api/patients/{patientId}/tests
 -> 后端保存文件
 -> 后端调用 Python /predict
 -> Python 返回 result 和 probability
 -> 后端写入 test_record 表
 -> 返回检测记录
```

## 7. 关键设计决策

| 决策 | 说明 |
| --- | --- |
| 前后端分离 | 便于练习真实 Web 开发流程 |
| Java 后端调用 Python 服务 | 避免 Java 直接耦合 Python 模型代码 |
| 先使用假模型服务 | 降低早期开发风险，先跑通系统闭环 |
| 文件由 Java 后端保存 | 便于检测记录保存影像路径 |
| 接口统一返回格式 | 降低前端处理复杂度 |

## 8. 当前限制

- 本阶段只支持本机运行。
- 文件存储使用本地目录，不使用对象存储。
- 暂不处理用户权限和数据隔离。
- 暂不处理真实医疗场景下的数据安全和合规要求。

