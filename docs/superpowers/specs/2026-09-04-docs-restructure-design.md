# Documentation Restructuring Design

## Goal

Restructure project documentation to provide a clear information hierarchy: README for quick start, /doc for detailed understanding.

## Audience

Competition project - readers need to understand how to run the project and why features are designed this way. No contribution guidelines needed.

## Current State

| File | Lines | Status |
|------|-------|--------|
| README.md | 232 | Complete, keep mostly unchanged |
| docs/evaluation.md | 42 | Brief, needs expansion |
| docs/report.md | 31 | Placeholder |

## Target Structure

```
MiiDi/
├── README.md              # Entry point: quick start + architecture overview + links to /doc
├── docs/
│   ├── architecture.md    # Architecture details: module responsibilities, data flow, design decisions
│   ├── evaluation.md      # Evaluation system: dual-track architecture, experiment methods, scoring criteria
│   ├── pipeline.md        # Generation pipeline: 5-stage details, configuration parameters
│   ├── styles.md          # Style system: 5 genres, knowledge pack structure
│   ├── api.md             # API documentation: endpoints, request/response formats
│   └── report.md          # Experiment report: E1/E2/E3 results analysis
```

## File Responsibilities

| File | Content | Link Location in README |
|------|---------|------------------------|
| README.md | Quick start, features, architecture diagram | — |
| architecture.md | Module dependencies, data models, technical rationale | "架构概览" section |
| evaluation.md | Dual-track scoring, 6-axis details, experiment design | "评测体系" section |
| pipeline.md | 5-stage details, configuration, resume from breakpoint | "分阶段生成" section |
| styles.md | 5 genres, knowledge pack structure, how to extend | "五种曲风" section |
| api.md | Complete REST API documentation | "API 端点" section |
| report.md | Experiment results, data analysis, conclusions | "实验报告" section |

## Design Principles

1. **README stays concise** - no major changes, just add links to /doc
2. **Each /doc file is self-contained** - can be read independently
3. **Progressive disclosure** - overview → details → reference
4. **Chinese language** - all documentation in Simplified Chinese
5. **Humanizer-zh** - follow Humanizer-zh principles to remove AI writing patterns:
   - 删除填充短语，打破公式结构
   - 变化节奏，混合句子长度
   - 信任读者，直接陈述事实
   - 删除金句，避免夸大的象征意义
   - 避免三段式法则、否定式排比、AI 词汇

## Implementation Plan

1. Create docs/architecture.md
2. Expand docs/evaluation.md
3. Create docs/pipeline.md
4. Create docs/styles.md
5. Create docs/api.md
6. Update docs/report.md
7. Update README.md with links to /doc files

All documentation will be written in Simplified Chinese and processed through Humanizer-zh principles to ensure natural, human-like writing.
