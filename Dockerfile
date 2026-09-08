# ---- 前端构建 ----
FROM node:20-alpine AS web-build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- 运行时 ----
FROM python:3.11-slim
WORKDIR /app
# web/ 与 styles/ 均按源码位置 parents[3] 解析，必须从仓库布局运行而非 site-packages
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1
COPY pyproject.toml README.md ./
COPY src/ src/
COPY styles/ styles/
COPY web/ web/
RUN pip install --no-cache-dir .
COPY --from=web-build /build/dist web/dist
EXPOSE 8000
CMD ["python", "src/miidi/serve.py"]
