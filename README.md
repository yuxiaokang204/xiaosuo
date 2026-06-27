# 小说创作Agent系统

一个基于AI的小说创作助手，提供完整的小说创作工具链，包括大纲生成、正文撰写、角色管理等功能。

## 功能特性

- 📝 **智能大纲生成** - 根据主题自动生成小说大纲
- ✍️ **AI辅助创作** - 生成正文、续写、润色等功能
- 👥 **角色管理** - 完整的角色设定和管理系统
- 🌍 **世界观设定** - 创建和管理小说的世界观
- 💾 **本地存储** - 数据安全存储在本地
- 🎨 **美观界面** - 现代化的用户界面设计

## 技术栈

### 后端
- Python 3.10+
- FastAPI - Web框架
- SQLAlchemy - ORM
- SQLite - 数据库

### 前端
- React 18
- TypeScript
- Vite - 构建工具

## 快速开始

### 环境准备

确保你已安装：
- Python 3.10 或更高版本
- Node.js 16 或更高版本
- npm 或 yarn

### 安装后端依赖

```bash
cd /workspace
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
pip install -e .
```

### 安装前端依赖

```bash
npm install
```

### 启动服务

#### 方式一：分别启动

启动后端服务：
```bash
python run.py
```

启动前端开发服务器：
```bash
npm run dev
```

#### 方式二：使用concurrently（推荐）

```bash
# 首先安装concurrently
npm install -g concurrently

# 然后启动
concurrently "python run.py" "npm run dev"
```

### 访问应用

- 前端地址：http://localhost:8080
- 后端API：http://localhost:8080
- API文档：http://localhost:8080/docs

## 项目结构

```
/workspace
├── src/
│   ├── backend/              # 后端代码
│   │   ├── agents/          # AI Agent模块
│   │   ├── core/            # 核心逻辑
│   │   ├── api/             # API路由
│   │   ├── db/              # 数据库相关
│   │   └── models/          # 数据模型
│   └── frontend/            # 前端代码
│       └── src/
│           ├── components/   # React组件
│           ├── types.ts     # TypeScript类型
│           └── api.ts       # API客户端
├── pyproject.toml          # Python项目配置
├── package.json            # Node.js项目配置
└── README.md               # 项目文档
```

## 使用指南

### 创建新小说

1. 点击首页的「+ 新建小说」按钮
2. 填写小说标题、类型和目标字数
3. 点击「创建」

### 生成大纲

1. 进入小说编辑页面
2. 切换到「大纲」标签
3. 输入主题，点击「生成大纲」

### 撰写正文

1. 在「编辑器」标签选择章节
2. 点击「生成正文」让AI帮你写
3. 或直接在编辑器中手动输入
4. 点击「续写」继续创作

## 开发说明

### 后端开发

- 数据库模型：`src/backend/db/models.py`
- API路由：`src/backend/api/`
- Agent实现：`src/backend/agents/`

### 前端开发

- 组件位置：`src/frontend/src/components/`
- 样式文件：`*.module.css`
- API调用：`src/frontend/src/api.ts`

## 许可证

MIT License
