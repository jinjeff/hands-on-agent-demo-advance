# 高级实战（P1–P8）

本目录是一门 **hands-on 实战课程的完整工程**：从第一部分「对话壳 + SSE 水管」做到第六部分「全链路验收」，再往下还有第七部分「多用户隔离」、第八部分「Workspace 与 Memory」两个进阶模块。全程只在这一个目录里操作。

课程用**一个环境变量 `MODE` 贯穿所有阶段**——后端 `server.py` 按 `echo` / `p3` / `p4` / `agent` 切换行为，前端从第一部分之后零改动；无 Key 保命路径（mock 三模式）全程可走。

配套文档：`实战步骤.md`（课堂步骤，八个部分）、`验收记录表.md`（P6 签字）、`security-checklist.md`（安全五条）。

## 目录结构

```text
高级实战/
├── 实战步骤.md            # 实战步骤（P1–P6 基础 + P7/P8 进阶，大步骤分小节）
├── 验收记录表.md           # P6 总判定签字
├── README.md              # 本文件
├── docker-compose.yml     # P5 拓扑草图（config 校验用）
├── compose.venv.yml       # P5 本地极速模式（挂宿主机 venv，跳过 build）
├── ci-cd.github-actions.yml
├── security-checklist.md  # 安全五条
├── frontend/              # Vue3 + @matechat/core（第一部分装一次 npm i，后续只用 npm run dev）
│   └── src/useSSE.ts      # SSE 流式解析（含中文乱码、半行 JSON 两个修法）
├── backend/               # 四种 MODE 的 SSE 后端（.venv 与 .env.example 都在这里）
│   ├── workspace_mgr.py   # 第八部分：工作区 + AgentRuntime 生命周期
│   ├── memory.py          # 第八部分：按用户隔离的长期记忆
│   └── ws.Dockerfile      # 第八部分：docker 工作区基础镜像（带 uv）
├── scripts/retrieve.py    # P2 三问检索（打真 RAGFlow /api/v1/retrieval）
└── 样本/                  # 采购合同（电子版 / 扫描件）
```

## 一张端口表

| 端口 | 服务 | 起它的阶段 |
|---|---|---|
| 5173 | frontend（vite） | P1 起，全程 |
| 8000 | backend 主服务 | 全程 |
| 80 / 9380 | RAGFlow 控制台 / API | 第二部分配好；第三、四部分经 MCP 复用 |
| 8001 | A2A Server | P4 |
| 8002 | MCP Server | P4 |

## 三分钟跑通（无 Key 保命路径）

```bash
# 终端 1：主服务（P1 回声）
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
$env:MODE="echo"                # Windows；macOS/Linux 用 MODE=echo 前缀
uvicorn server:app --reload --port 8000

# 终端 2：前端
cd frontend && npm install && npm run dev
```

浏览器开 `http://127.0.0.1:5173`，随便输入一句，应能看到气泡逐字出现「回声：…」。之后按 `实战步骤.md` 逐部分推进；第二部分起接入本机真实 RAGFlow（控制台 `http://127.0.0.1`，API `9380`）。

> Windows 用户注意：`实战步骤.md` 的命令按 macOS/Linux 书写，PowerShell 里的对应写法是——激活 venv 用 `.venv\Scripts\Activate.ps1`，设环境变量用 `$env:MODE="echo"`，复制文件用 `copy .env.example .env`。

## 课前环境

Node 20+ / Python 3.11+（AgentScope 需要）/ Docker（第二、五部分用，装法见下文与 `实战步骤.md` 导读 0.1）。裸进程版第一到第四部分不需要 Docker。详见 `实战步骤.md` 第一部分「课前检查」。

## 在 Windows 上安装 Docker Desktop

第二部分（RAGFlow）和第五部分（整套 compose）需要 Docker。Windows 装 **Docker Desktop** 一个即可，它自带 Engine + Compose 插件。

### 1. 前置条件

| 项 | 要求 | 检查 / 处理 |
|---|---|---|
| 系统 | Windows 10 64 位（版本 2004 / 内部版本 19041 以上）或 Windows 11 | `winver` 查看 |
| 虚拟化 | CPU 开启 VT-x/AMD-V 且 BIOS 里启用 | 任务管理器 → 性能 → CPU，「虚拟化」应为「已启用」；关闭 Hyper-V 冲突软件（如 VMware 旧版、VirtualBox） |
| WSL2 | 推荐用 WSL2 后端（官方默认，比 Hyper-V 后端快） | 以管理员身份运行 PowerShell：`wsl --install`，装完重启；已有 Linux 发行版则 `wsl --update` |
| 磁盘 | ≥ 30 GB 空闲 | RAGFlow 五个镜像 + 向量数据很占地 |
| 内存 | ≥ 16 GB（RAGFlow 用；只跑第五部分 8 GB 够） | DeepDoc 解析吃内存，不足会静默卡死 |

### 2. 安装

1. 到 Docker 官网下载 Docker Desktop for Windows 安装包（也可用国内镜像源下载）；
2. 双击安装，**勾选「Use WSL 2 instead of Hyper-V」**（默认已勾，别取消）；
3. 装完重启电脑，启动 Docker Desktop，等托盘图标变绿（Engine running）。

### 3. 调设置（关键，默认值不够用）

Settings → Resources：

- **Memory**：拖到 **≥ 12 GB**（默认只有 2–4 GB，RAGFlow 起不来）；
- **Disk image size**：≥ 60 GB；
- 国内网络可在 Settings → Docker Engine 里配镜像加速：

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me",
    "https://docker.m.daocloud.io"
  ]
}
```

改完点 Apply & Restart。公共加速器时开时关，**拉不动就换一个**。

### 4. 验证三行（PowerShell）

```powershell
docker --version          # 期望 ≥ 24.02
docker compose version    # 期望 v2.26+；注意是 docker compose（有空格），不是 docker-compose
docker run --rm hello-world
```

第三条能拉镜像并打印 `Hello from Docker!` 即全通。

### 5. Windows 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `WSL 2 installation is incomplete` / 提示装内核更新 | 没装 WSL2 或内核旧 | 管理员 PowerShell 跑 `wsl --install` + `wsl --update`，重启 |
| 安装时提示未启用虚拟化 | BIOS 里 VT-x/AMD-V 没开 | 进 BIOS 打开 CPU 虚拟化 |
| 托盘图标一直转 / Engine 起不来 | WSL 发行版未初始化或冲突 | `wsl --shutdown` 后重开 Docker Desktop；或 Settings → General 里取消 WSL 试 Hyper-V 后端 |
| `permission denied` 拉镜像 | 没登录或加速器失效 | Docker Desktop 菜单里 Sign in；换 registry-mirrors |
| `docker-compose: command not found` | 用了带横杠的 v1 写法 | 本课程一律 `docker compose`（有空格） |
| 中文目录名 compose 报 `project name must not be empty` | 项目名从目录名推导为空 | 本目录 `docker-compose.yml` 已固定顶层 `name: kb-agent`，直接可用 |
| 容器访问不到宿主机上的 RAGFlow | 容器里 `127.0.0.1` 是它自己 | compose 已统一用 `host.docker.internal`（Windows Desktop 默认支持解析） |
| 源码放 `C:\Users\...` 挂载奇慢 | Docker Desktop 跨系统文件 IO | 把课程目录放进 WSL2 文件系统（如 `\\wsl.localhost\Ubuntu\home\you\...`）会快很多 |

> 装好 Docker 后，RAGFlow 的部署在 `实战步骤.md` 第二部分 2.0.1，整套 compose 在第五部分 5.3。**只想做第一到第四部分的裸进程版，Docker 全程可以不装。**
