# 医学影像分类系统原型

这是一个本地运行的医学影像分类系统原型，整体采用前后端分离结构：

- `medical-web`：Vue 3 + Vite 前端，用于影像检测、患者信息管理、操作记录、模型测评。
- `medical-system`：Spring Boot 后端，负责业务接口、数据库读写、转发模型服务请求。
- `python-api`：FastAPI + PyTorch 模型服务，负责影像推理和批量模型测评。

当前项目面向本机开发和课程验收场景，默认不考虑公网部署。

## 功能

### 影像检测

医生侧单次检测页面，前端选择一个病人文件夹，保持上传图片模式。系统会解析病人目录、展示 Cine/LGE 图像、调用模型服务得到二分类结果，并把患者和检测记录写入数据库。

支持的病人目录格式：

```text
Patient_001/
  Cine/
    SA/
      Location_01/
        Frame_01.png
        Frame_02.png
  LGE/
    Location_01.png
    Location_02.png
```

### 患者信息

支持患者信息的新增、查询、排序、编辑、删除。列表会展示最近一次检测结果和检测时间。

### 操作记录

记录关键操作日志，支持单条删除和一键清空。

### 模型测评

验收侧批量测评页面，前端不上传大量图片，只提交本地数据集路径。后端把路径转发给 Python 模型服务，由 Python 服务在本机直接读取数据并生成测评结果。

支持的测评目录格式：

```text
Final_test_data/
  Cine/
    Patient_001/
      SA/
        Location_01/
          Frame_01.png
  LGE/
    Patient_001/
      Location_01.png
```

输出结果包含 `patient_index` 和 `mace_score`，前端表格展示并支持下载 `output_table.xlsx`。

## 环境要求

- Windows 10/11
- Java 21
- Maven 3.9+
- Node.js 20+
- Python 3.10+
- MySQL 8+

## 数据库准备

创建数据库和项目账号：

```sql
CREATE DATABASE medical_system
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER 'medical_user'@'localhost' IDENTIFIED BY 'your_password';

GRANT ALL PRIVILEGES ON medical_system.* TO 'medical_user'@'localhost';

FLUSH PRIVILEGES;
```

在 `medical-system/src/main/resources/application.properties` 中配置数据库连接：

```properties
spring.datasource.url=jdbc:mysql://localhost:3306/medical_system?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
spring.datasource.username=medical_user
spring.datasource.password=your_password
```

核心表：

```sql
CREATE TABLE patients (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  gender VARCHAR(10) NOT NULL,
  age INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE test_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  patient_id BIGINT NOT NULL,
  result VARCHAR(50) NOT NULL,
  confidence DECIMAL(8,6),
  tested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255),
  CONSTRAINT fk_test_records_patient
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
```

操作记录表由后端启动后自动创建。

## 模型文件

模型权重默认放在：

```text
python-api/output/
```

需要包含：

```text
Cine_img_model_checkpoint.pth
LGE_img_model_checkpoint.pth
TTST_SequenceTraining_checkpoint.pth
```

## 运行方式

### 1. 启动 Python 模型服务

```powershell
cd python-api
..\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

如果已经激活虚拟环境：

```powershell
python -m uvicorn app:app --reload --port 8000
```

### 2. 启动 Java 后端

```powershell
cd medical-system
mvn spring-boot:run
```

后端默认运行在：

```text
http://localhost:8080
```

### 3. 启动 Vue 前端

```powershell
cd medical-web
npm.cmd install
npm.cmd run dev
```

前端默认运行在：

```text
http://localhost:5173
```

### 4. 一键启动脚本

根目录提供了 `start-dev.ps1`，用于开发时同时拉起三个服务。首次运行前仍需要先完成数据库、依赖和模型文件配置。

```powershell
.\start-dev.ps1
```

## 常用接口

### Java 后端

- `GET /api/health`：后端健康检查
- `POST /api/predict`：影像检测，上传病人图像文件
- `GET /api/patients`：患者列表、搜索、排序
- `POST /api/patients`：新增患者
- `PUT /api/patients/{id}`：修改患者
- `DELETE /api/patients/{id}`：删除患者
- `GET /api/patients/{id}/records`：查看患者检测记录
- `POST /api/model-evaluation-path`：提交本地测评数据集路径
- `GET /api/operation-logs`：操作记录列表

### Python 模型服务

- `GET /health`：模型服务健康检查
- `POST /predict`：上传图像推理
- `POST /predict-path`：本地路径推理
- `POST /evaluate-path`：本地测评数据集推理

## 验证命令

```powershell
cd medical-system
mvn -q -DskipTests compile
```

```powershell
cd medical-web
npm.cmd run build
```

```powershell
cd python-api
..\.venv\Scripts\python.exe -B -m py_compile app.py run_test.py
```

## 目录说明

```text
medical-web/      前端项目
medical-system/   Java 后端项目
python-api/       Python 模型服务
start-dev.ps1     本地开发启动脚本
README.md         项目说明
```
