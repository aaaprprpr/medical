# Medical System Documentation

本目录用于维护医学影像二分类系统原型的开发文档。

当前项目定位是本地学习型原型系统，不作为真实医疗诊断系统使用。

## 文档清单

| 文档 | 说明 |
| --- | --- |
| [01-requirements.md](./01-requirements.md) | 需求说明，定义项目目标、范围、功能与验收标准 |
| [02-architecture.md](./02-architecture.md) | 架构说明，定义前端、Java 后端、数据库、Python 模型服务的关系 |
| [03-api.md](./03-api.md) | API 设计，定义前后端接口和后端调用模型服务的接口 |
| [04-database.md](./04-database.md) | 数据库设计，定义患者表和检测记录表 |
| [05-dev-plan.md](./05-dev-plan.md) | 开发计划，定义阶段目标、优先级和验证方式 |

## 当前约定

- 前端：Vue，本地端口 `5173`
- 后端：Spring Boot，本地端口 `8080`
- 模型服务：Python FastAPI，本地端口 `8000`
- 数据库：开发初期可用 H2，稳定后切换 MySQL
- 接口风格：REST API
- 数据格式：JSON
- 文件上传：`multipart/form-data`

