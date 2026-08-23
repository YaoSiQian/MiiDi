# MiiDi

基于 LLM 的符号音乐（MIDI）生成与双轨评估系统。

## 状态

Kernel 核心（schema / 渲染 / 规则评估器）已实现；生成流水线、Web 应用与评测材料按计划推进（见 docs/superpowers/specs/ 与 docs/superpowers/plans/）。

## 安装

    pip install -e ".[dev]"
    cp env.example .env   # 填入 OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME

## 运行测试

    python -m pytest tests/ -v

## 设计文档

- 规格：docs/superpowers/specs/2026-08-22-miidi-design.md
- 计划：docs/superpowers/plans/
