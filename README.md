# 仙侠打斗导演 v1.4

面向仙侠、玄幻、修仙题材的战斗与特效镜头创作技能。特效由视频模型直接生成：描述形态、运动、接触、人物回应、光照和环境后果；Niagara 等名称仅作视觉参考。

完整战斗交付设计卡、资产提示词、导演分镜、关键帧、视频执行稿、审阅摘要。单项特效或局部修改只交付用户所需内容。包内是规则、示例和校验工具，不含生成媒体或外部生成 API。

## 快速使用

将整个目录放入所用宿主支持的技能目录，保持 `SKILL.md` 位于技能目录根层；具体安装位置和触发方式以宿主规则为准。

可以直接提出任务：

- **完整战斗**：设计30秒山门救人戏。筑基符修不能打赢金丹守卫，只能破坏阵眼，让师弟逃走。给完整六件套，三维国漫风格。
- **单项特效**：给一个液金连续覆甲的视频提示词。右手伤势保留，左手一直持剑，最后用有甲的前臂挡住飞石。
- **局部修改**：把火墙改成逐步凝固的冰墙，保留逃生结局，更新相关状态、关键帧、光照和视频提示词。

普通创作使用自然语言，不需要 Python 或 JSON。已有设定和素材优先，未实际读取的素材不作观察结论。

## 阅读与目录

| 内容 | 入口 |
| --- | --- |
| 技能规则、交付范围与按需路由 | [SKILL.md](SKILL.md) |
| 20类视觉特效、40个差异短例 | [特效类型库](references/effects-library.md) |
| 24种应用、12种转场、6种变身 | [特效应用库](references/effects-applications.md) |
| 直接生成、参考职责与定向返修 | [特效生成规范](references/effects-generation.md) |
| 八个可复制的专项场面 | [应用案例](examples/effects-application-cases.md) |
| 攻防、修炼机制、连续性、摄影、资产与画风 | `references/`，按技能入口选择 |
| 四套完整战斗及七文件交付 | `examples/01-*` 至 `examples/04-*` |
| 工作JSON字段、版本和工具边界 | [交付契约](references/delivery-contract.md) |
| 局部修改与语义审阅 | [审阅与修复](references/review-and-repair.md) |

特效类型说明画面怎样表现，应用说明它承担什么任务；二者可组合，不要求每场凑齐。连续变身和关键交互必须保留，不能用遮挡后换外观代替。

## JSON与工具

技能包版本 **1.4**，完整战斗工作 JSON 版本 **1.3**；**1.1、1.2** 保留原规则与导出兼容。独立疗伤、仪式、天气等短镜默认用自然语言，不强套完整战斗存档。

脚本使用 Python 3.10+，仅依赖标准库。在本目录执行：

```bash
python scripts/combat_plan.py validate examples/01-sword-and-body.json
python scripts/combat_plan.py export examples/01-sword-and-body.json --out ./my-battle-output
python -B -m unittest discover -s tests -v
```

`--out` 必须是父目录已存在的新目录，不覆盖已有文件或目录。每次导出六篇 Markdown 和 `project.json`。1.3 的03导演稿链接06审阅稿，不重复嵌入整篇审阅；旧版导出不变。

校验器检查字段、引用、时轴、共享状态和效果阶段关系。`structural_status: pass` 不证明动作、空间、观感或模型执行成立；`semantic_status` 保持 `needs_review`。JSON时间为成片时间，当前不支持精确世界／成片双时轴。

## 维护与来源

- [版本记录](CHANGELOG.md)：主要变化与兼容范围。
- [当前验证](VERIFICATION.md)：检查命令、结果及未验证范围。
- [历史行为记录](tests/behavior/README.md)：按版本保留原始请求、答复和评阅，不当作当前成功率。
- `tests/fixtures/compat/`：冻结的旧版输入与预期输出，用于兼容回归；公开示例中的 `project.json` 则用于完整交付快照。
- [第三方声明](THIRD_PARTY_NOTICES.md)与 `sources.json`：方法参考、来源指纹和许可说明。上游资料不作为运行依赖，本包未替权利人确定整体开源许可证。
