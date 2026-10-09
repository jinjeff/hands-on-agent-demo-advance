# 四个后端服务（agent-api / mcp / a2a / 可选的真 Agent）共用同一个镜像。
# 依赖在 build 时装进镜像层——第一次 build 约 40+ 秒，之后 up 秒起，改代码也不用重建
# （源码通过 volume 挂载进容器，改完 reload 生效）。
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（这一层被缓存，requirements.txt 不变就不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码（改代码只会让这一层失效，不影响上面的依赖层）
COPY . .

# 不在挂载目录里留 __pycache__（否则会在宿主机源码树里留下 root 属主文件）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
