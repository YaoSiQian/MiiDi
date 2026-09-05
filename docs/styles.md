# 曲风知识包

MiiDi 内置五种曲风，每种风格配备独立的知识包（knowledge pack），存放在 `skills/` 目录下。知识包为 LLM 生成流水线提供风格专属的音乐语言约束，确保输出符合特定曲风的审美标准。

## 曲风一览

| 风格 | BPM 范围 | Swing | 鼓组 | 一句话 |
|------|----------|-------|------|--------|
| **pop** | 84-132 | 无 | 有 | 明亮的四件套乐队，大调主导，I-V-vi-IV 和声骨架 |
| **classical** | 60-168 | 无 | 无 | 室内管弦乐语境，功能和声，声部写作，无打击乐 |
| **jazz** | 110-208 | 200 tick | 有 | 小型组合摇摆，walk bass，七和弦为默认和弦质量 |
| **lofi** | 66-92 | 180 tick | 有 | 卧室低保真，Rhodes maj7/min7/9，慵懒拖拍 |
| **touhou** | 120-170 | 无 | 有 | 高能同人电子摇滚，多层和声织体，E7-Am 终止式 |

## 各风格详解

### Pop 流行

明亮的四件套乐队语境：鼓、电贝斯、钢琴或吉他伴奏，加一条好记的主旋律。以大调/小调自然音阶为基础，围绕 I-V-vi-IV 进行构建，乐句结构清晰，backbeat 稳定推进。

**配器：** Lead 2 (sawtooth) 做旋律，Electric Piano 1 (Rhodes) 做和声，Electric Bass (finger) 做低音，Pad 2 (warm) 做色彩铺底。音域不重叠，避免超过一个旋律声部。

**鼓组模式：** kick 落在拍头和第三拍，snare 在 2/4 拍，hat 八分音符均匀铺满。无 swing offset。

**和声语汇：** 大调 I-V-vi-IV 家族，支持变体（IV-I-V-vi 等）。避免平行五八度，和弦支撑旋律音。

### Classical 古典

室内管弦乐语境，建立在功能和声之上：清晰的主-属极性、声部导向的对位写作、动机发展贯穿稳定乐段。不使用鼓组，律动完全靠各声部记谱体现。

**配器：** 无固定配器表，由用户指定。常见组合包括弦乐四重奏、木管重奏、钢琴独奏等。所有声部必须在合理音域内。

**节奏特征：** 密度参考值最低（全局 2-16 事件/小节），留白多，乐句呼吸感强。无 drum_patterns。

**和声语汇：** 功能和声体系，主-下属-属-主的基本逻辑。支持七和弦、转位、经过和弦。注重声部连接的平滑性。

### Jazz 爵士

小型组合摇摆语境，110-208 BPM。ride 摇摆脉冲、walking bass、钢琴伴奏下接管乐主旋律。七和弦是默认和弦质量，所有进行倾向于 ii-V-I 运动，带松弛的摇摆感。

**配器：** 未在 instruments.md 中固定配器，由用户在 plan 阶段指定。典型组合：萨克斯/小号主奏、钢琴伴奏、爵士贝斯、鼓组。

**鼓组模式：** kick 低强调（feathered），snare comping 重音，hat 走 ride cymbal 的 2-and-4 反拍。swing offset 200 tick。

**节奏特征：** 八分音符走 swing，bass 走四分音符（walking quarter）。offbeat 位置延迟 200 tick 形成 lilt。

**和声语汇：** 七和弦为默认，ii-V-I 为核心进行。支持替代和弦、tritone substitution、modal interchange。

### Lofi 低保真

慵懒的卧室 chillhop，66-92 BPM。稀疏织体、dusty Rhodes 的 maj7/min7/9 色彩、拖拍的懒洋洋鼓点。不完美是美学——柔和力度、少量音符、深沉的宁静感。

**配器：** Rhodes 电钢琴做和声，简单贝斯线，轻柔鼓组。音符密度低，留白多。

**鼓组模式：** kick 在拍头稍拖后（1020 tick），snare 在 480/1560（略偏移），hat 反拍（120, 600, 1080, 1560）。swing offset 180 tick，制造拖拍感。

**节奏特征：** 整体密度偏低，鼓点松弛，swing 让八分音符产生慵懒摇摆。力度普遍偏弱。

**和声语汇：** maj7/min7/9 色彩和弦，避免强烈属功能进行。喜欢挂留和弦、add9、无根音 voicing。

### Touhou 东方

高能同人电子摇滚，120-170 BPM。多层和声织体（弦乐 + 羽管键琴 + 钢琴 + 管风琴）堆叠出密集和弦 pad，synth bass 走锁定的八分音符驱动，方波/锯波 lead 携带明亮的小调旋律。直 16 分音符推进，零 swing，从头到尾持续高能。终止式落在硬正格终止（E7-Am）带全乐队重音。

**配器：** 多层和声织体是核心特征。弦乐、羽管键琴、钢琴、管风琴同时铺底，创造厚度。synth bass 八分音符持续驱动。square/saw lead 做旋律。

**鼓组模式：** kick 密集（每 360 tick 一次），snare 在 2/4 拍，hat 十六分音符铺满。无 swing，直拍驱动。

**和声语汇：** A 小调为主调。核心进行：Am-F-G-Am（ZUN 循环）、Am-G-F-E7（皇家道路下行）、Dm-E7-Am（iv-V7-i）。E7-Am 终止式是整个风格最标志性的和声动作——E7 中的升 G 创造导音，拉向 A 小调。

**节奏特征：** 全局密度最高（10-48 事件/小节），十六分音符持续驱动，无 swing，鼓组和 bass 高度同步。

## 知识包结构

每个风格的目录包含 5 个必需文件：

```
skills/{style}/
├── SKILL.md         # 风格概览：身份定位、工作流、输出规则
├── instruments.md   # 配器表：角色、GM 音色、音域、注意事项
├── harmony.md       # 和声语汇：和弦符号表、特征进行、调性中心
├── rhythm.md        # 节奏特征：鼓组模式、网格说明、swing 参数
└── defaults.json    # 默认参数：BPM 范围、密度参考、swing offset、鼓 pattern
```

### defaults.json 格式

```json
{
  "bpm_range": [min, max],
  "density_ref": {
    "__global__": [min, max],
    "melody": [min, max],
    "harmony": [min, max],
    "bass": [min, max]
  },
  "swing_offsets": [tick_offset, ...],
  "drum_patterns": {
    "kick": [tick, ...],
    "snare": [tick, ...],
    "hat": [tick, ...]
  }
}
```

**字段说明：**
- `bpm_range`：风格的合法速度区间
- `density_ref`：各角色每小节事件数的参考范围，`__global__` 是总密度
- `swing_offsets`：offbeat 位置的延迟 tick 数，空数组表示直拍
- `drum_patterns`：各鼓件的打击时间点（tick），仅流行/爵士/lofi/东方有

### 加载机制

`src/miidi/skills/loader.py` 负责加载知识包：

- `load_style_pack(name)` 读取指定风格目录，解析所有文件，返回 `StylePack` 数据类
- `available_styles()` 扫描 `skills/` 目录，返回所有包含 `defaults.json` 的子目录名
- 缺少任何必需文件会抛出 `FileNotFoundError`
- `defaults.json` 格式错误会抛出 `ValueError`

环境变量 `MIIDI_SKILLS_DIR` 可覆盖默认的 `skills/` 目录位置。

## 扩展新风格

添加新风格只需两步：

### 1. 创建目录和文件

在 `skills/` 下新建目录，放入 5 个必需文件：

```bash
mkdir skills/mygenre
touch skills/mygenre/{SKILL.md,instruments.md,harmony.md,rhythm.md,defaults.json}
```

### 2. 填写内容

**SKILL.md** — 写清楚三件事：
- 风格的一句话身份定位
- 工作流（可以复制现有风格的模板）
- 输出规则（JSON schema 要求）

**defaults.json** — 参考现有风格填写：

```json
{
  "bpm_range": [70, 120],
  "density_ref": {
    "__global__": [4, 20],
    "melody": [3, 10],
    "harmony": [2, 8],
    "bass": [1, 5]
  },
  "swing_offsets": [],
  "drum_patterns": {
    "kick": [0, 960],
    "snare": [480, 1440],
    "hat": [0, 480, 960, 1440]
  }
}
```

**其余三个 .md** — 按照乐器表、和声语汇、节奏特征的结构撰写。参考已有的风格包来把握详细程度。

### 验证

添加完成后运行：

```bash
# 确认新风格被识别
python -m miidi styles

# 加载测试
python -c "from miidi.skills.loader import load_style_pack; p = load_style_pack('mygenre'); print(p.name)"
```

## 风格相关的评估维度

评估系统中有多处与风格直接相关：

### 规则轨中的风格参数

| 轴 | 使用风格数据的地方 |
|----|-------------------|
| **A2 和声正确性** | 和弦支撑度检查依赖 `harmony.md` 中的和弦表 |
| **A4 节奏律动** | 鼓 pattern 匹配度对照 `defaults.json` 的 `drum_patterns` |
| **A5 结构与发展性** | 段落覆盖度参考 `SKILL.md` 中的结构描述 |

### 反退化门中的风格约束

- **G_density**：密度上限取自 `defaults.json` 的 `density_ref.__global__`
- **G_balance**：声部平衡检查参考各角色的密度参考值

### Judge 轨的风格评判

- **J1 风格符合度**：逐条对照 `SKILL.md` 中的风格特征清单
  - pop：是否有 I-V-vi-IV 进行、backbeat 鼓组、单旋律 lead
  - classical：是否无鼓组、功能和声、声部连接
  - jazz：是否有 swing feel、walking bass、七和弦
  - lofi：是否有低 BPM、稀疏织体、拖拍鼓点
  - touhou：是否有高密度、E7-Am 终止式、多层织体

### 新风格的评估适配

添加新风格后，如果现有评估规则不够用，可以在 `eval/axes/` 下新增风格专属的检测逻辑。例如：
- 如果新风格有独特的终止式要求，可在 A2 轴中添加终止式检测
- 如果新风格有特殊的鼓组规则，可在 A4 轴中扩展 drum pattern 匹配
- J1 的特征清单需要在 prompt 中更新，加入新风格的特征条目
