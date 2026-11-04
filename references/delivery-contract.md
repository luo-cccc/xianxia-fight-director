# 交付契约 v1.1

本契约用于单场战斗的可选工作JSON。日常创作默认自然语言；用户要求存档与导出时使用JSON。数据由创作者编写，工具只检查结构、计算时码与组织文本，不推导动作、不将结构通过等同成片通过。

技能包v1.2沿用本契约1.1，不新增字段或迁移要求。以下身份/状态、支点和尺度约束属于作者语义审阅，不能由结构校验自动证明。

## 时间、层级与版本

所有数字时间均为**成片全场秒数**，不是世界经过秒数；制作段执行稿由工具减去段起点，转换为段内秒数。允许有限小数，比较容差 `1e-6`，拒绝布尔值、NaN、Infinity和非有限大数。

- `beats`：动作因果的完整定义，允许并行与跨镜。`requires`仅代表前拍完成后才能开始；部分进展触发写在动作文本，不伪造完成依赖。
- `shots`：主剪辑从0连续覆盖总时长。引用的节拍须与镜头有正时长交集，所有引用窗口并集覆盖完整节拍。
- `segments`：沿整镜切分，每镜按原序恰好分配一次；不预设平台时长上限。
- `keyframes`：镜内指定成片时刻，每镜至少一张，切点上明确所属镜头。
- 慢镜：导演稿说明成片窗口、放慢的动作阶段、同窗各方如何同步。JSON数字不再代表现实速度或事件耗时；精确事件/呈现双时轴、重放和插叙不由本契约表达，不能宣称支持。
- 每个区间满足 `0 <= start < end <= duration_sec`。

版本字符串为 `1.1`。1.0包含混用时码的自由文本，不能可靠自动迁移；工具明确拒绝旧版本。迁移时由创作者补写当前镜头执行窗口，检查状态并重新导出，不能用正则批量替换数字来冒充迁移。

## 根对象

```text
schema_version: "1.1"
title: 非空字符串
duration_sec: 正有限数字
aspect_ratio: 非空字符串（创作设定，不是平台能力声明）
style: 非空字符串
assumptions: 字符串列表，可空
constraints: 字符串列表，可空
design: {goals, rules, turns, outcome, viewing_tasks?}
assets: 非空资产数组
scene: {asset_id, geography}
beats: 非空节拍数组
shots: 非空镜头数组
segments: 非空制作段数组
keyframes: 非空关键帧数组
review?: 审阅登记对象
```

所有对象拒绝未知字段。`goals`明确双方实际任务；`rules`和`turns`为非空字符串列表，`outcome`为非空字符串。可选`viewing_tasks`为非空字符串列表，仅用于记录导演观看任务，不进入执行稿。

`scene.asset_id`引用 `scene` 资产；`geography`为非空字符串，明确总体战场、地标、距离与高度。本版一场战斗一个总体战场，多个地标在其中组织。

## 资产

```text
{id, kind, name, anchors, states, image_prompt, reference?}
```

- 所有资产、节拍、镜头、制作段、关键帧使用同一全场唯一ID空间，格式 `[A-Za-z][A-Za-z0-9_-]*`。
- `kind`: `character | creature | scene | prop | formation | manifestation`。
- `name`、`image_prompt`非空；`anchors`非空字符串列表；`states`字符串列表，可空。
- `anchors`只放本场需要持续识别的身份、服装结构与器形。持物手、姿势、新伤、湿损及亮灭等时变内容放在`states`、镜头状态与执行文本中；资产图指定站姿或持物不成为永久锚点。已有资产先继承，不重建无关外观。
- `states`登记本场可能用到的状态变化，不是各镜同时成立的属性集合。执行稿仍只取资产锚点，由当前镜头状态和cue写出本窗口实际状态，不全量输出未来损伤或失效。
- 可选`reference`严格为 `{source,control,keep,exclude}`，各非空字符串。未读图可写source“用户路径（读取失败，待核实）”、control“身份外观，具体待核实”、keep“仅继承用户文字已确认的白衣等，其余待核实”、exclude“原姿势与背景不作为本场要求”；不杜撰图片细节。
- 精确路径读取失败，只允许必要的直接父目录核对，不扩大搜索磁盘、桌面或下载目录。

## 节拍与完整导演稿

```text
{id, start, end, actors, action, response, result, requires}
```

`actors`非空、无重复，只引用`character/creature/manifestation`；`requires`无重复节拍ID，可空，不自引、不成环、不依赖未来完成的拍。`action/response/result`非空；无即时回应也说明受限或主动不行动的依据。

完整节拍可有全场时码、因果与资源说明，仅进入设计/分镜导演稿。跨镜时，导演稿允许展示完整定义并标观察窗口，**执行稿不得照搬完整节拍**。

## 镜头与执行窗口

```text
{id, start, end, beat_ids, asset_ids, opening_state, camera, effects, sound,
 end_state, execution}
execution: {opening_state, end_state, camera, effects, sound, cues}
cue: {start, end, text}
```

- `beat_ids`非空、无重复且引用有效；`asset_ids`非空、无重复，登记本镜可见或需绑定资产，包括必要画外状态，不让画外人凭空消失。
- 外层`opening_state/end_state`为完整世界状态；相邻镜头外层前终态与后起态逐字相等。机位和构图单列，不混入共享世界状态。
- 接触或移动成立所需的支撑面、可用肢体、持物手、来去路径与动势写入既有状态和行动文字；空间高度统一零点，绝对高度与相对高差明确区分，不另建姿态或坐标字段。
- 外层`camera/effects/sound`非空，供完整导演稿使用。效果描述来源、路径/范围、作用点、残留/消退，声音不默认配乐。
- `execution`是创作者另写的**简洁当前镜头窗口**，不是工具从自由文本截取。五项文本非空：当前起态、终态、摄影、特效、声音。相邻镜`execution`前终态与后起态逐字相等；精简状态仍包含下一镜成立的关键信息。
- `cues`非空数组，按序从本镜起点连续覆盖到终点，无缺口重叠，每项`text`只写当前窗口实际行动、回应与结果。数字`start/end`仍是全场成片时刻，渲染时才减段起点。
- 执行文本不写阿拉伯数字的秒码或冒号时码，时刻仅使用cue数值字段。可以写“向北三步”“保持接点”，不要写“24秒开始”或“0:12”。工具仅识别常见数字秒码与时码，不声称穷尽所有自然语言时间。
- 跨镜拍第一镜写起手和当时结果，后镜从既有相位继续，不重放已经完成的起手、伤害或后续结果。
- 执行文本不得含全场未来结局、内部依赖ID、测试目的、长篇能力解析。它应是可见/可听行动，不是设计说明。

## 制作段

```text
{id, shot_ids, opening_state, closing_state, prompt_context}
```

`shot_ids`按序拼接等于主镜头数组；段首末状态逐字等于首镜起态/末镜终态，相邻段终起态逐字相等。

`prompt_context`非空字符串，只含本段需要的空间、能力、资源与画外持续状态，使用名称而非内部ID，不写数字时码或全场未来结局。起终态位置/高度、动势、持物、持续术法/在途攻击、伤损与限制要能独立恢复，不使用“同上”。

执行稿自动选本段镜头`asset_ids`的并集，只打印资产名称、锚点与参考绑定；必要的画外施术者或器物应显式纳入对应镜头，而不是无条件输出全场资产。各段从0起的时码独立，不混全场时间。

## 关键帧

```text
{id, shot_id, time_sec, asset_ids, state, prompt}
```

引用有效镜头和资产；资产非空、无重复且属于该镜资产集合；时刻位于所属镜头闭区间。`state/prompt`非空，只写那一瞬间可见的姿态、接点、器物、光照、环境，不画完整动作链。

静态姿态与正文符合程度须语义审阅。关键帧导出仍列全场与段内时刻供制作绑定，不能把这些元数据一股脑混入视频执行正文。

## 审阅及媒体观察

可选`review`必含：`{scope,fixed,pending,invalidated,verification}`，其中scope/verification非空字符串，fixed/pending/invalidated为字符串列表，可空。

可选子字段 `media_observations` 是数组，可空；每项严格 `{source,kind,observation,limitations}`，各字符串非空，kind为`image|video|audio`。记录作者实际依据及限制，不因为生成提示词就登记为已观察。

脚本始终只判定自身结构操作，语义状态为`needs_review`。作者登记的文本/媒体观察原样列出，不自动判通过。没有条目时写“未登记媒体观察”，不推断图片是否已生成、是否曾被查看；不再硬编码`not_generated`或“没有观看”。

完整交付需要实际审阅摘要；没有review时输出明确待补的骨架，不把它称为已完成语义审阅。

## 工具与输出

```bash
python scripts/combat_plan.py validate examples/01-sword-and-body.json
python scripts/combat_plan.py export examples/01-sword-and-body.json --out /path/to/new-directory
```

失败退出1、参数错误退出2；重复JSON键、非法常量、无效编码均拒绝。新目录导出前检查并在内存渲染，已有文件/目录不覆盖，失败清理本次临时产物。

输出仍为七文件：`project.json`、`01-design.md`、`02-assets.md`、`03-storyboard.md`、`04-keyframes.md`、`05-video-prompts.md`、`06-review.md`。其中03是完整导演稿，05是逐段精简执行稿；二者用途不同。

工具不判断空间可达、招式合理、动作耗时、观感、具体平台能力或模型服从程度。执行稿长度按真实需要控制，没有平台品牌通用的安全字数阈值；写平台专属请求前先确认版本、入口和模式。
