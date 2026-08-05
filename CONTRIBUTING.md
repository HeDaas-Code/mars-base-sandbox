# 贡献指南

感谢你对赫拉克勒斯协议项目的关注！

## 开发环境

### 环境要求

- Python 3.10+
- Node.js 18+ (前端开发可选)
- Git

### 本地开发设置

```bash
# 克隆仓库
git clone <repo-url>
cd <repo-name>

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
export LLM_API_KEY="your-api-key"
```

## 分支策略

- `main` — 稳定分支，仅通过 PR 合并
- `feature/<name>` — 功能开发分支
- `fix/<name>` — Bug 修复分支
- `docs/<name>` — 文档更新分支

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <description>

feat(agent): 添加 NPC 人格模板渲染
fix(scheduler): 修复事件 TTL 过期逻辑
docs(readme): 更新快速开始指南
refactor(ws): 重构 WebSocket 消息分发
test(game_loop): 添加结局判定单测
```

类型：`feat` | `fix` | `docs` | `refactor` | `test` | `chore` | `style`

## 代码风格

- Python: 遵循 PEP 8
- 使用 4 空格缩进
- 函数/类添加 docstring（Google 风格）
- 类型注解（Python 3.10+ 语法）

## 测试

```bash
# 运行全部测试
cd backend
python -m pytest ../tests/

# 运行特定测试
python -m pytest ../tests/test_game_loop.py -v
```

## Pull Request 流程

1. Fork 仓库并创建功能分支
2. 编写代码并添加测试
3. 确保所有测试通过
4. 提交 PR，描述变更内容和原因
5. 等待代码审查

## 项目结构约定

- `backend/` — 后端 Python 代码
- `frontend/` — 前端 JS/CSS/HTML
- `dict/` — 游戏数据 YAML（由游戏策划维护）
- `docs/` — 项目文档
- `tests/` — 测试文件

## 联系方式

如有问题，请通过 Issue 或 PR 评论联系。