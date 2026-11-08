# GitHub 相似项目检索

检索日期：2026-11-04。以当前可访问的 GitHub 仓库页、README，以及特别注明的技能说明页为依据。下表“参考价值”为结合本项目需求作出的分析，不代表已经运行或验证对方的生成效果。

## 本次新增发现

| 项目 | 已读内容与定位 | 对本项目的参考价值（分析） |
| --- | --- | --- |
| [qualsenWeb/fight-video-create-skill](https://github.com/qualsenWeb/fight-video-create-skill) | README：从想法或素材检索动作，组织主攻、防守、反击和统一打斗段落；提供动作、运镜、机甲等资料检索工具。 | 适合研究如何检索招式与镜头词汇，并把动作组成有回应的攻防链；其部分资料加密，不能仅据README判断全部资料内容。 |
| [liyue-aigc/xianxia-cinematic-video-director](https://github.com/liyue-aigc/xianxia-cinematic-video-director) | README：仙侠动作视频导演，以逐镜景别、运镜、起止姿态、动作链、特效、受力与环境反馈组织提示词。 | 与本项目视频执行稿最接近，可对照逐镜身体支点、镜头边界、剑路和环境反馈；注意保留本项目对手回应与任务目标。 |
| [liyue-aigc/xianxia-visual-director](https://github.com/liyue-aigc/xianxia-visual-director) | 本次复核README：仙侠环境与视觉档案设计，强调巨物尺度、空间分层、建筑承重和环境秩序，具体提示词交给下游。 | 适合补强场景资产、法相与人物的同框尺度证明；视觉档案不能代替动作因果和时间设计。 |
| [62656456/ai-film-skills](https://github.com/62656456/ai-film-skills) | README及[人物资产合同](https://github.com/62656456/ai-film-skills/blob/main/docs/skills/zh-CN/character-asset.md)：覆盖人物、场景、道具、分镜、武侠动作及实验性白模预演；人物合同分开稳定身份与允许状态变化。 | 最适合参考稳定特征、可变状态和下游引用的分离，减少本次持物锚点类冲突。技能说明页标有整改候选或实验状态，应逐模块判断。 |

## 已有来源的线上复核

以下两项已在本项目`sources.json`登记，本次确认当前GitHub页面可访问，不计为新增来源。当前在线版本可能与历史ZIP指纹不同；本次没有修改历史来源证据。

| 项目 | 当前README的定位 | 对照重点（分析） |
| --- | --- | --- |
| [lixiaoxiao9888-create/xuanhuan-combat-director](https://github.com/lixiaoxiao9888-create/xuanhuan-combat-director) | 玄幻仙侠打斗提示词，包含攻守节奏、镜头、特效尺度、兵器招式和角色场景预设。 | 题材最接近，可比较招式及尺度表达。其固定三轮攻守和反杀结构与本项目按任务决定结局的原则不同，不应直接替代现有规则。 |
| [liyue-aigc/seedance-2-5-fight-director](https://github.com/liyue-aigc/seedance-2-5-fight-director) | 面向Seedance 2.5的打斗提示词、分镜、分段承接和已有提示词诊断。 | 适合研究通用导演稿的具体平台适配及诊断表达；仓库README本身也说明规格以实际入口为准。 |

## 优先阅读顺序

1. `ai-film-skills`的人物资产合同：研究如何清楚分开稳定身份与持物、姿态、伤损等可变状态。
2. `xianxia-cinematic-video-director`：对照镜头起止姿态、身体支点和环境受力反馈。
3. `xianxia-visual-director`：补充巨物与空间的视觉表达。
4. `fight-video-create-skill`：评估动作资料检索是否能减少泛化招式表达。

初始检索阶段只形成对比记录；后续方法吸收见下节。没有安装上游技能、接入生成API或复制上游正文与代码。

## v1.2 实际采纳与删减 · 2026-11-04

随后按用户要求完成方法吸收。四项方法参考的读取文件、提交和SHA-256已登记到`sources.json.web_sources`；历史ZIP指纹保持原样。

| 来源方法 | 实际落点 | 取舍 |
| --- | --- | --- |
| 人物资产合同的身份/状态分离 | 资产参考、交付契约、入口与三套示例 | 保留现有`anchors/states`，不新增并行资产合同，不把未来状态全量送入执行稿。 |
| 逐镜起止姿态和受力 | 摄影、连续性、审阅参考 | 将支点、可用肢体、路径和身体/环境回应写进既有状态与动作；不强制每镜填动作学表。 |
| 仙侠环境与巨物表达 | 资产、摄影与连续性参考 | 统一高度口径，以同框参照说明尺度，区分主风与局部冲击；不固定五层空间或每镜尺寸。 |
| 动作资料检索与攻防衔接 | 战斗设计参考 | 采用按任务、距离、持物与支撑选择具体行为的方法；不接入上游检索脚本或加密库，资料读取是可选项。 |

删去入口和摄影参考中重复的JSON字段列表，合并分散的篇幅预算、平台和媒体证据说明。未采用固定三轮攻守、反杀结局、未经核实的平台参数或强制联网。工作JSON继续使用1.1，工具字段与命令不变。
