# NAS Toolbox

NAS Toolbox 是一个面向 Linux NAS 的轻量 Web 文件工具箱。后端使用 Python 和 FastAPI，前端使用 Vue 3 与 Vite，默认通过 Docker 运行，不依赖数据库、Redis 或任务队列。

删除操作始终遵循“扫描 → 查看结果 → 用户确认 → 删除”的流程。扫描结果仅短暂保存在当前进程内存中，30 分钟后自动失效，应用重启后也会失效。

## 当前工具

### 删除空文件夹

- 自底向上递归识别空目录，因此 `A/B` 中 `B` 为空、删除 `B` 后 `A` 也为空时，两者都会出现在扫描结果中。
- 永远不删除用户输入的扫描根目录。
- 不跟随 symbolic link。
- 无权限或无法读取的目录会跳过，并显示在错误列表中。
- 删除前由操作系统再次确认目录确实为空；扫描后出现新文件时不会误删。

### 重复文件检测

- 提供四种可选策略：精确文件重复、PCM 音频内容、相似音频、同名文件。
- 精确模式先按文件大小分组，只对大小相同的候选文件计算 MD5。
- PCM 模式通过 FFmpeg 对解码后的音频帧计算 SHA-256，可忽略 WAV/FLAC 容器标签差异。
- 相似音频模式通过 Chromaprint 查找可能是同一首歌的不同编码或母带版本。
- 同名模式忽略文件名大小写，查找不同目录下名称相同的文件。
- MD5 以 2 MiB 分块流式读取，不会把大文件整体载入内存。
- 展示扫描文件数、重复组数、可删除副本数和预计可释放空间。
- 每组选择一个文件保留，确认后删除其他副本。
- 删除前重新检查每个文件是否存在，并重新验证大小和 MD5；任一成员发生变化时跳过整组。

相似音频和同名文件只属于候选提示，不代表内容完全相同。界面会显示人工确认警告，尤其是原版、精选版、重制版和不同母带可能都应保留。所有策略仍必须由用户逐组选择并二次确认，绝不会扫描后自动删除。

> MD5 在这里用于内容去重，不用于安全认证。

生产镜像已包含 FFmpeg、ffprobe 和 fpcalc（Chromaprint）。本地直接运行音频策略时也需要安装这些命令；精确文件和同名文件策略不依赖它们。

## Docker Compose 部署

1. 在 Docker Hub 创建名为 `nas-toolbox` 的仓库，或者直接使用已经发布的镜像。
2. 修改 `docker-compose.yml` 中的镜像用户名，也可以通过环境变量传入：

   ```bash
   export DOCKERHUB_USERNAME=yourname
   ```

3. 按 NAS 的真实目录调整 volumes 和 `ALLOWED_ROOTS`：

   ```yaml
   services:
     nas-toolbox:
       image: yourname/nas-toolbox:latest
       container_name: nas-toolbox
       restart: unless-stopped
       ports:
         - "17701:17701"
       volumes:
         - /mnt:/mnt
         - /data:/data
       environment:
         - ALLOWED_ROOTS=/mnt,/data
         - TZ=Asia/Shanghai
   ```

4. 启动服务：

   ```bash
   docker compose pull
   docker compose up -d
   ```

浏览器打开 `http://NAS_IP:17701`。以后更新只需再次运行上面的 `pull` 和 `up -d`。

### Volume 映射与权限

容器只能看到通过 `volumes` 映射进去的目录。若要删除文件，映射不能带 `:ro`，并且容器进程必须拥有宿主目录的读取和删除权限。建议只映射实际需要管理的路径，不要映射宿主机的 `/`。

路径在 Web 页面中应填写容器内路径。例如宿主 `/volume1/photos` 映射为 `/mnt/photos` 后，页面中使用 `/mnt/photos`。

## ALLOWED_ROOTS 路径边界

`ALLOWED_ROOTS` 是逗号分隔的绝对路径列表，例如：

```text
ALLOWED_ROOTS=/mnt,/data
```

应用只允许扫描这些根目录及其子目录。统一路径校验会拒绝相对路径、`..`、不存在的路径和允许范围外的路径，并解析真实路径以阻止 symbolic link 跳出边界。目录扫描本身也不会跟随 symbolic link。

Volume 决定“容器能看到什么”，`ALLOWED_ROOTS` 决定“Web 应用允许操作什么”；两者应保持一致并遵循最小权限原则。

## 本地开发

需要 Python 3.12+、Node.js 22+ 和 [uv](https://docs.astral.sh/uv/)。先构建 Vue 前端，再启动 FastAPI。Linux/macOS 示例：

```bash
uv sync
npm --prefix frontend install
npm --prefix frontend run build
export ALLOWED_ROOTS=/tmp/nas-toolbox-data
mkdir -p /tmp/nas-toolbox-data
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 17701
```

PowerShell：

```powershell
uv sync
npm --prefix frontend install
npm --prefix frontend run build
$env:ALLOWED_ROOTS = "D:\data"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 17701
```

开发前端时可以分别启动后端和 Vite 开发服务器：

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 17701
npm --prefix frontend run dev
```

Vite 开发页面位于 `http://localhost:5173`，并会将 `/api` 代理到 FastAPI。生产构建会把 Vue、JavaScript 和 CSS 内嵌到单个 HTML 文件中，以兼容 FN Connect 中继和带路径前缀的反向代理。

运行测试：

```bash
uv run pytest
```

构建本地镜像：

```bash
docker build -t nas-toolbox:local .
```

## GitHub Actions / Docker Hub 发布

`.github/workflows/docker.yml` 在代码 push 到 `main` 时构建并推送镜像。请在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 添加：

- `DOCKERHUB_USERNAME`：Docker Hub 用户名。
- `DOCKERHUB_TOKEN`：具有目标仓库写权限的 Docker Hub access token，不要使用明文密码。

工作流发布两个标签：

- `DOCKERHUB_USERNAME/nas-toolbox:latest`
- `DOCKERHUB_USERNAME/nas-toolbox:sha-<完整提交 SHA>`

## 项目结构

```text
nas-toolbox/
├── app/
│   ├── api/                 # HTTP 路由与请求模型
│   ├── services/            # 空目录、重复文件等核心业务逻辑
│   ├── utils/               # 路径安全和流式哈希等公共能力
│   ├── frontend_dist/       # Vite 生成的单文件生产页面
│   ├── config.py
│   └── main.py              # 应用组装与路由注册
├── frontend/
│   ├── src/components/      # Vue 工具页面与共享组件
│   ├── src/api.js           # 中继路径兼容的 API 客户端
│   ├── src/App.vue
│   └── vite.config.js
├── tests/
├── .github/workflows/docker.yml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

API 只处理 HTTP 输入输出，Service 不依赖 FastAPI，便于单独测试；路径验证和哈希等可复用能力集中在 utils。Vue 前端通过 Hash 路由切换工具，因此反向代理不需要处理前端路由回退。

## Adding a New Tool

增加工具通常不需要修改现有工具，按以下边界添加模块即可：

1. 在 `app/services/` 新增一个 service，例如 `file_search.py`，实现纯 Python 核心逻辑。所有用户路径必须调用 `app/utils/filesystem.py` 中的统一验证函数；危险操作要保持“预览后确认”。
2. 在 `app/api/` 新增路由模块，定义请求/响应，将 HTTP 参数交给 service，并在 `app/main.py` 注册 router。
3. 在 `frontend/src/components/` 新增 Vue 工具组件，在 `App.vue` 注册 Hash 路由，并在 `Dashboard.vue` 添加工具卡片。网络请求统一复用 `frontend/src/api.js`，以保持 FN 中继路径兼容。
4. 在 `tests/` 使用 `tmp_path` 为 service 和关键 API 添加测试，绝不依赖或修改真实 NAS 文件。
5. 如果引入系统命令或额外权限，在 Dockerfile、Compose 和 README 中明确说明。不要让整个容器默认获得不必要的特权。

未来工具可按同样方式扩展：

- **批量重命名**：service 生成旧名/新名预览，确认时重新检查冲突后执行。
- **7z 解压**：service 校验目标路径并限制压缩包条目，防止解压路径穿越；镜像中单独安装 7z。
- **文件搜索**：service 只读遍历，复用错误收集和路径边界。
- **SMART**：独立 service 包装 `smartctl`，Compose 仅授予必要设备访问权限。
- **Docker 管理**：独立 API/service，并明确 Docker socket 带来的宿主机级权限风险。
- **网络测速**：独立 service 执行受控测速任务，不与文件工具耦合。

对于耗时工具，第一步仍应优先使用简单的同步或应用内任务实现；只有实际需求证明有必要时，再评估额外基础设施。

## 安全说明

NAS Toolbox 是面向受信任局域网的管理工具，当前版本不包含登录认证。不要直接暴露到公网；如需远程访问，请在反向代理或 VPN 层添加 HTTPS 和身份认证。删除前仍应确保重要数据已有可靠备份。
