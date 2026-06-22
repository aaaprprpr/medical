# 开发计划

## 1. 开发原则

- 先跑通最小闭环，再逐步整理结构。
- 前端负责展示和发请求，不承担正式数据库查询逻辑。
- Java 后端负责业务接口、数据库访问和模型服务编排。
- Python 服务只负责模型推理。
- 每完成一个稳定阶段，同步更新文档。

## 2. 已完成

### 2.1 前端

- Vue + Vite 项目创建。
- 顶部菜单栏。
- 影像检测页面左右布局。
- 患者文件夹选择。
- Cine/LGE 图像解析。
- Cine Location 切换。
- 缩略图相册。
- 单图查看器。
- 上一张、下一张、关闭按钮。
- 多文件上传到 Java 后端。
- 预测结果展示，结果中文化，置信度格式化。

### 2.2 Python 模型服务

- FastAPI 服务。
- `/health` 健康检查。
- `/predict` 多文件接收。
- 临时还原患者目录。
- 调用真实模型推理。
- 推理结束后清理临时文件。
- 只作为计算服务，不访问数据库。

### 2.3 Java 后端

- Spring Boot 项目。
- `/api/health` 健康检查。
- `/api/predict` 多文件接收和转发。
- MySQL 连接。
- `patients` 表基础 CRUD。
- 患者搜索和排序。

## 3. 当前阶段

当前重点：患者信息模块。

已经完成后端：

```text
GET    /api/patients
GET    /api/patients/{id}
POST   /api/patients
PUT    /api/patients/{id}
DELETE /api/patients/{id}
```

已经支持：

```text
keyword
gender
sortBy
order
```

下一步建议：

1. 前端患者信息页接入患者列表接口。
2. 前端完成新增、编辑、删除按钮和表单。
3. 前端搜索面板调用后端搜索接口。
4. 表头点击时传 `sortBy` 和 `order` 给后端。

## 4. 下一阶段

### 4.1 检测记录表

新增 `test_records` 表，保存每次检测结果。

目标：

- 保存患者 ID。
- 保存模型结果。
- 保存置信度。
- 保存代表图像名。
- 保存检测时间。

### 4.2 联表查询

患者列表增加最近检测摘要：

```text
最近检测结果
最近检测时间
最近图像
```

该信息由 `patients` 和 `test_records` 联表查询得到。

### 4.3 分页

患者列表后续增加分页：

```http
GET /api/patients?page=1&pageSize=10
```

## 5. 后续整理任务

- 删除或保留 `DatabaseController` 需要明确：当前它只是数据库连接测试接口。
- 患者接口可以后续增加参数校验。
- 错误响应可以后续统一封装。
- `Controller -> Repository` 后续可以拆为 `Controller -> Service -> Repository`。
- 可以增加基础测试，保留 `src/test` 用于后续学习。

## 6. 暂不处理

- 登录注册。
- 权限控制。
- 正式部署。
- 医疗合规。
- 多用户协作。
- 真实报告导出。
- 图像长期存储策略。
