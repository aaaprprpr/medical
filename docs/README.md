# 医学影像分类系统原型文档

这组文档记录当前项目的真实设计和开发状态。项目目标不是做生产级医疗系统，而是通过一个完整的前后端分离原型，练习 Java Web、数据库、接口文档、前端页面和 Python 模型服务协作。

## 阅读顺序

| 文件 | 用途 |
| --- | --- |
| `真-开发文档.md` | 当前工作台，记录现在做到哪、下一步做什么 |
| `01-requirements.md` | 需求说明，描述系统要解决什么问题 |
| `02-architecture.md` | 架构说明，描述前端、Java 后端、Python 服务、数据库的关系 |
| `03-api.md` | 接口文档，记录 Apifox 和前端要调用的 HTTP 接口 |
| `04-database.md` | 数据库设计，记录表结构、字段含义和 SQL |
| `05-dev-plan.md` | 开发计划，记录已完成、待完成和暂不处理的内容 |

## 当前状态

已经完成：

- 影像检测页面。
- Vue 前端选择患者文件夹、解析 Cine/LGE 图像、浏览缩略图和单图。
- 前端多文件上传到 Java 后端。
- Java 后端转发多文件到 Python FastAPI 模型服务。
- Python 服务执行真实模型推理并返回结果。
- MySQL 接入。
- 患者表 `patients` 的基础 CRUD、搜索和排序。

正在推进：

- 患者信息页前后端联调。
- 后续检测记录表 `test_records` 设计和联表查询。

## 项目模块

```text
medical-web/
  Vue + Vite 前端

medical-system/
  Spring Boot Java 后端

python-api/
  FastAPI + PyTorch 模型服务

docs/
  项目文档
```

## 本地服务端口

| 服务 | 地址 |
| --- | --- |
| Vue 前端 | `http://localhost:5173` |
| Java 后端 | `http://localhost:8080` |
| Python 模型服务 | `http://localhost:8000` |
| MySQL | `localhost:3306` |

## 文档维护约定

- 改接口时同步改 `03-api.md`。
- 改表结构时同步改 `04-database.md`。
- 阶段完成后同步改 `05-dev-plan.md`。
- 临时想法放 `真-开发文档.md`，稳定后再整理进正式文档。
