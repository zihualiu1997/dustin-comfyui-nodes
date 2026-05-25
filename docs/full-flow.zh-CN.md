# ComfyUI 节点包完整流程

这份文档按“先本地能用，再放到 GitHub，再发布到 Registry，最后让 Manager 能更新”的顺序写，适合以后重复照着走。

## 1. 先理解几个核心概念

- `Git`：本地版本管理工具，负责记录每一次改动。
- `GitHub`：托管 Git 仓库的网站，用来备份、协作、公开发布代码。
- `仓库`：一个项目的文件和历史记录。
- `commit`：一次本地保存点。
- `push`：把本地提交上传到 GitHub。
- `Comfy Registry`：Comfy 官方的节点注册和分发入口。
- `ComfyUI-Manager`：用户搜索、安装、更新节点的界面，当前主链路依赖 Registry。

## 2. 你的日常开发循环

每次新增节点或更新节点，都尽量按这个节奏做：

```text
写代码 -> 本地测试 -> 更新 README -> 修改版本号 -> git add -> git commit -> git push -> comfy node publish
```

## 3. 本地开发

1. 把这个仓库放进 `ComfyUI/custom_nodes/`。
2. 重启 ComfyUI。
3. 在节点搜索中查找 `Dustin Text Prefix`。
4. 先确认最小节点可以加载，再继续添加更复杂节点。

如果节点没有出现，优先检查：

- 仓库根目录是否有 `__init__.py`
- `NODE_CLASS_MAPPINGS` 是否正确导出
- Python 是否报 import 错误
- 节点类中的 `FUNCTION`、`RETURN_TYPES`、`INPUT_TYPES` 是否拼写正确

## 4. 创建 GitHub 仓库

推荐流程：

1. 登录 GitHub。
2. 新建一个公开仓库，比如 `dustin-comfyui-nodes`。
3. 不必在网页里额外初始化 README，因为本地已经有文件了。
4. 记下仓库地址，例如 `https://github.com/<你的用户名>/dustin-comfyui-nodes`。

本地初始化仓库后，常用命令是：

```powershell
git init
git add .
git commit -m "Create initial ComfyUI node package"
git branch -M main
git remote add origin https://github.com/<你的用户名>/dustin-comfyui-nodes.git
git push -u origin main
```

如果你更喜欢图形界面，也可以用 GitHub Desktop 完成 `publish repository`。

## 5. 填写 Registry 元数据

发布前至少要确认 `pyproject.toml` 里的这些字段已经换成真实值：

- `[project].name`
- `[project].version`
- `[project.urls].Repository`
- `[tool.comfy].PublisherId`
- `[tool.comfy].DisplayName`

注意：

- `name` 是节点包的唯一标识，首次发布后不要随便改。
- `version` 必须是 `X.Y.Z` 形式。
- `PublisherId` 来自 Comfy Registry 上你自己的 publisher。

## 6. 安装 comfy-cli

如果机器上还没有 `comfy` 命令，可以先安装：

```powershell
python -m pip install --user comfy-cli
```

安装后确认：

```powershell
comfy --version
```

## 7. 创建 Registry Publisher

1. 打开 [registry.comfy.org](https://registry.comfy.org/)。
2. 登录并创建 publisher。
3. 记下 `@` 后面的 `PublisherId`。
4. 进入 publisher 页面创建 API key。
5. 先安全保存这个 key。

## 8. 第一次手动发布

先把 `pyproject.toml` 改成真实值，然后在仓库目录执行：

```powershell
comfy node publish
```

终端会要求输入 API key。发布成功后，你会拿到一个 Registry 页面地址。

建议第一次先手动发布，因为这样最容易理解整个过程。

## 9. 让 GitHub 自动发布

当你已经手动发布成功一次后，再考虑自动化。

### 9.1 添加 GitHub Secret

在 GitHub 仓库中创建一个 secret：

- 名称：`REGISTRY_ACCESS_TOKEN`
- 值：刚才创建的 Registry API key

### 9.2 工作流文件

本仓库已经准备好 `.github/workflows/publish.yml`，以后只要你更新 `pyproject.toml` 的版本并推送到 `main`，GitHub Actions 就会自动发布。

## 10. 版本号怎么加

- 修 bug：`0.1.0` -> `0.1.1`
- 加一个新节点：`0.1.0` -> `0.2.0`
- 做破坏兼容的改动：`0.1.0` -> `1.0.0`

Registry 上已发布版本不能覆盖，所以每次都必须升版本号。

## 11. 以后添加新节点的固定步骤

1. 在 `nodes/` 里新建一个 Python 文件或新类。
2. 在 `nodes/__init__.py` 里导出这个类。
3. 在仓库根 `__init__.py` 中确认映射仍然正确。
4. 更新 `README.md`。
5. 本地重启 ComfyUI 测试。
6. 更新 `pyproject.toml` 的 `version`。
7. 推送到 GitHub。
8. 手动或自动发布到 Registry。

## 12. 常见卡点

- `gh` 命令不存在：说明 GitHub CLI 未安装，不影响你用网页或 GitHub Desktop。
- `comfy` 命令不存在：先安装 `comfy-cli`。
- 节点没加载：先看 ComfyUI 启动日志里的 Python 报错。
- Manager 里搜不到：通常是还没发布到 Registry，或者版本发布失败。
