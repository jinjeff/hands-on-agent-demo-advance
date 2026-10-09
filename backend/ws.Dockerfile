# DockerWorkspace 的基础镜像（第八部分可选后端）
#
# 为什么需要它：AgentScope 的 DockerWorkspace 会在容器里执行 `uv venv` 建虚拟环境，
# 官方 python 镜像没有 uv，直接用会报 DockerStreamError。所以自己烤一个：
#
#   docker build -t kb-agent-ws:latest -f ws.Dockerfile .
#   # .env 里：WORKSPACE_BACKEND=docker  WS_IMAGE=kb-agent-ws:latest
FROM python:3.11-slim

RUN pip install --no-cache-dir uv
