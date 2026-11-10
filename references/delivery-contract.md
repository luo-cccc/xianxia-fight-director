# 交付契约 v1.4

本契约用于单场战斗的可选工作JSON。日常创作默认自然语言；用户要求存档与导出时使用JSON。数据由创作者编写，工具只检查结构、计算时码与组织文本，不推导动作、不将结构通过等同成片通过。

**只接受 `schema_version: "1.4"`。1.0、1.1、1.2、1.3 旧存档不再兼容，工具直接拒绝，也不提供自动迁移；旧稿需按本契约重写。** 本契约包含编舞字段、分层字段与生成窗口规划；窗口规划让“一次生成多长、从哪里切”由剧本关联决定，而不是由平台默认时长决定。

## 时间与层级

所有数字时间均为**成片全场秒数**，不是世界经过秒数；制作段执行稿由工具减去段起点，转换为段内秒数。允许有限小数，比较容差 `1e-6`，拒绝布尔值、NaN、Infinity和非有限大数。

- `beats`：动作因果的完整定义，允许并行与跨镜。`requires`仅代表前拍完成后才能开始；部分进展触发写在动作文本，不伪造完成依赖。边界相接是允许的：前拍 `end` 恰等于后拍 `start` 视为"已完成"（按 `1e-6` 容差），不必留空隙。一个节拍可被多个镜头引用、各引用窗口可相接，只要并集完整覆盖该拍。
- `shots`：主剪辑从0连续覆盖总时长。引用的节拍须与镜头有正时长交集，所有引用窗口并集覆盖完整节拍。
- `segments`：沿整镜切分，每镜按原序恰好分配一次；不预设平台时长上限。
- `keyframes`：镜内指定成片时刻，每镜至少一张，切点上明确所属镜头。
- 慢镜：导演稿说明成片窗口、放慢的动作阶段、同窗各方如何同步。JSON数字不再代表现实速度或事件耗时；精确事件/呈现双时轴、重放和插叙不由本契约表达，不能宣称支持。
- 每个区间满足 `0 <= start < end <= duration_sec`。

`schema_version` 只接受字符串 `"1.4"`。其他值（含 1.0、1.1、1.2、1.3、1.5）直接拒绝；不提供迁移命令，也不自动改写自由文本。

## 根对象

```text
schema_version: "1.4"
title: 非空字符串
duration_sec: 正有限数字
aspect_ratio: 非空字符串（创作设定，不是平台能力声明）
style: 非空字符串
assumptions: 字符串列表，可空
constraints: 字符串列表，可空
design: {goals, rules, turns, outcome, viewing_tasks?}
assets: 非空资产数组
scene: {asset_id, geography, attrition}        # 必填
beats: 非空节拍数组
shots: 非空镜头数组
segments: 非空制作段数组
keyframes: 非空关键帧数组
cost: 非空代价数组                              # 必填
knowledge?: 非空所知/实际数组                    # 可选
tracks?: 动作线数组                             # 可选
vfx?: 签名特效数组                               # 可选
forms?: 形态切换数组                             # 可选
transitions?: 转场数组                           # 可选
window_plan?: 生成窗口规划对象                   # 可选
review?: 审阅登记对象
```

所有对象拒绝未知字段。`goals`、`rules`、`turns` 三者都是**非空字符串列表**（`goals` 通常一方一条，写各自要达成什么，不写成对象或单个字符串），`outcome`为非空字符串。可选`viewing_tasks`为非空字符串列表，仅用于记录导演观看任务，不进入执行稿。

`scene.asset_id`引用 `scene` 资产；`geography`为非空字符串，明确总体战场、地标、距离与高度。一场战斗一个总体战场，多个地标在其中组织；识海等意识空间另建场景资产，用 `tracks` 区分。

## 战场累积痕迹

```text
scene.attrition: [{id, mark, from_beat, consequence}]
```

非空数组。`mark`写痕迹本身（焦痕、积水、碎石、霜槽、断口），`from_beat`引用造成它的节拍，`consequence`写它此后如何限制路线或与后续效果互动。ID进入全场唯一空间。

**可查后果**：至少一项痕迹的来源节拍在最早的关键转折开始之前结束。边界取**不晚于**，即来源拍的 `end` 恰等于最早 `pivotal` 拍的 `start` 也算通过（按 `1e-6` 容差比较）。地形要先被改变，才能约束决胜时刻的选择；否则痕迹只是结算清单。痕迹是否真的在后续镜头被尊重，属语义审阅。

## 资产

```text
{id, kind, name, anchors, states, image_prompt, reference?}
```

- 所有资产、节拍、镜头、制作段、关键帧、痕迹、代价、所知项，以及动作线、签名特效、形态切换、转场，使用同一全场唯一ID空间，格式 `[A-Za-z][A-Za-z0-9_-]*`。
- `kind`: `character | creature | scene | prop | formation | manifestation`。
- `name`、`image_prompt`非空；`anchors`非空字符串列表；`states`字符串列表，可空。
- `anchors`只放本场需要持续识别的身份、服装结构与器形。持物手、姿势、新伤、湿损及亮灭等时变内容放在`states`、镜头状态与执行文本中；资产图指定站姿或持物不成为永久锚点。已有资产先继承，不重建无关外观。
- `states`登记本场可能用到的状态变化，不是各镜同时成立的属性集合。执行稿仍只取资产锚点，由当前镜头状态和cue写出本窗口实际状态，不全量输出未来损伤或失效。
- 可选`reference`严格为 `{source,control,keep,exclude}`，各非空字符串。未读图可写source“用户路径（读取失败，待核实）”、control“身份外观，具体待核实”、keep“仅继承用户文字已确认的白衣等，其余待核实”、exclude“原姿势与背景不作为本场要求”；不杜撰图片细节。
- 精确路径读取失败，只允许必要的直接父目录核对，不扩大搜索磁盘、桌面或下载目录。

## 节拍与完整导演稿

```text
{id, start, end, actors, action, response, result, requires, marks?, track?}
```

`actors`非空、无重复，只引用`character/creature/manifestation`；`requires`无重复节拍ID，可空，不自引、不成环、不依赖未来完成的拍。`action/response/result`非空；无即时回应也说明受限或主动不行动的依据。

完整节拍可有全场时码、因果与资源说明，仅进入设计/分镜导演稿。跨镜时，导演稿允许展示完整定义并标观察窗口，**执行稿不得照搬完整节拍**。

### 节拍标记

可选`marks`为非空无重复数组，取值 `pivotal | breath | adaptation`。全场每种标记至少一处：

- **`pivotal` 关键转折**：优势结构真正改变的那一拍。它必须有预备、接触、结果三帧（见关键帧）。
- **`breath` 呼吸拍**：没有新攻击、只让观众看清已发生状态的短窗口。不能同时是`pivotal`，也不能与任何`pivotal`窗口重叠——它是爆发前后的停顿，不是爆发的一部分。**可以有多个**，每个都照样登记标记；"至少一处"是下限不是配额。符合定义的停顿就标上，不要因为已经有一个而让第二个在结构上无名无分；多个呼吸拍不会互相稀释，连续两拍都不出新攻击才是节奏问题，那属语义审阅。
- **`adaptation` 对手变招**：一方据已察觉的信息改变打法的那一拍。它的`requires`必须非空，指向被它回应的已完成前拍；没有前因的"变招"是预设剧本，不是适应。

一拍可带多个标记，例如决胜拍同时是`pivotal`和`adaptation`。标记只进导演稿，不进执行稿。

**这三项合起来定了一个硬下限：至少两个动作拍。** 因为呼吸拍不能兼任关键转折，所以最少要有一拍承担呼吸、另一拍承担转折（变招可以与转折同拍）。实测两镜两拍、总时长 2.4 秒的方案即可满足全部九条后果；单拍战斗无法用 1.4 表达——真的只有一次交手、没有任何停顿的场面请改用自然语言稿，不要为了凑标记硬拆出一个不存在的呼吸拍。

## 镜头与执行窗口

```text
{id, start, end, beat_ids, asset_ids, opening_state, camera, effects, sound,
 end_state, execution, light, risk, fallback?, track?, outer_state?}
execution: {opening_state, end_state, camera, effects, sound, light, cues}
cue: {start, end, text}
```

`light`、`risk` 与 `execution.light` 必填；`fallback` 由`risk`决定。

- `beat_ids`非空、无重复且引用有效；`asset_ids`非空、无重复，登记本镜可见或需绑定资产，包括必要画外状态，不让画外人凭空消失。
- 外层`opening_state/end_state`为完整世界状态；相邻镜头外层前终态与后起态逐字相等。机位和构图单列，不混入共享世界状态。
- 接触或移动成立所需的支撑面、可用肢体、持物手、来去路径与动势写入既有状态和行动文字；空间高度统一零点，绝对高度与相对高差明确区分，不另建姿态或坐标字段。
- 外层`camera/effects/sound`非空，供完整导演稿使用。效果描述来源、路径/范围、作用点、残留/消退，声音不默认配乐。
- `execution`是创作者另写的**简洁当前镜头窗口**，不是工具从自由文本截取。六项文本非空：当前起态、终态、摄影、特效、光照、声音。相邻镜`execution`前终态与后起态逐字相等；精简状态仍包含下一镜成立的关键信息。
- `cues`非空数组，按序从本镜起点连续覆盖到终点，无缺口重叠，每项`text`只写当前窗口实际行动、回应与结果。数字`start/end`仍是全场成片时刻，渲染时才减段起点。
- 执行文本不写阿拉伯数字的秒码或冒号时码，时刻仅使用cue数值字段。受检字段是 `execution` 的六项文本、`cues[].text`、`segments[].prompt_context`、`shots[].fallback`、`keyframes[].prompt`，以及会进入执行稿的资产 `name`、`anchors` 与 `reference` 各项（另加动作线、签名特效、窗口 `opening_state`／`closing_state`、`carries.text` 与 `fallback`）；**外层 `camera/effects/sound/light` 与外层世界状态属完整导演稿，允许写全场时码，不受此限**。
- 被禁的只是**时刻表达**：`22秒`、`0:12`、`01:02:03`、全角冒号时码。冒号时码指 `H:MM`、`MM:SS`、`H:MM:SS` 这类冒号后为两位数的写法，所以 `画幅16:9` 这类比例不受影响；检查前文本做 NFKC 归一化，全角数字同样受检。**计数与度量不受限制**——"退三步""两柄戟""离石面1.2米""八十厘米剑身"都可以照写，不必为了避险全改中文数字。
- 同样受检的还有**内部 ID 泄漏**：上面那批可复制文本里不得出现任何已登记的资产、节拍、镜头、制作段、关键帧、痕迹、代价、所知项、动作线、签名特效、形态切换或转场 ID。按词边界匹配，`B03` 这类短 ID 同样受检，但不会因为是别的词的一部分而误报。执行稿与静图提示词给的是可独立复制的内容，用名称而不是工程标识；"依赖 B03""承接 S02 的状态"这类写法会被拒绝。
- 跨镜拍第一镜写起手和当时结果，后镜从既有相位继续，不重放已经完成的起手、伤害或后续结果。
- 执行文本不得含全场未来结局、内部依赖ID、测试目的、长篇能力解析。它应是可见/可听行动，不是设计说明。

### 光照与归属

`light`写本镜主光来源、它属于谁的能力或环境、谁被压成暗部。仙侠战斗的光源多半就是双方的能力本身，所以"此刻画面被谁的光照亮"是免费的戏剧变量。

**可查后果**：全场`light`不得完全相同。战局转折处主光应改变来源或归属；全场一句"晴冷侧光"复制到底会被拒绝。一股持续术法光束是否真的照亮了它经过的岩壁与人脸，属语义审阅。

### 生成风险与保底构图

`risk`取 `low | high`。判据不是"这一镜难不难生成"，而是**"一次没拿到可用结果时，降级方式是否显然"**：

- 标 `high` 的是**承载了全场别处没有的那一件事**的镜头：决胜接点本身、巨物尺度的唯一同框参照、信息差被揭开的那一下、观众必须看懂的机制的唯一一次交代。这类内容在别处补不出来，一次没成就得有预先写好的退路。
- 标 `low` 的是**内容在别处也有、或可以重新编排**的镜头，哪怕它技术上同样不容易：换机位重拍、缩短窗口、少拍一个主体都不动摇后面的内容。段界末镜不因为"终态要交给下一段"就自动算 `high`——交接靠的是那张 `handoff` 静图和逐字共享的状态文本，不靠这一镜一次拍成。

**可查后果**：`high`必须附非空`fallback`，`low`不得附`fallback`。`fallback`写**同一份世界状态下更省的呈现方式**（遮挡、更短窗口、单主体、接点特写），不是改剧情，也不写时码。它进执行稿，作为一次生成失败后的现成降级路径，不破连续性。

**如果一场戏里过半镜头都被标 `high`，说明在量难度而不是量必要性**，回头按上面两条重标。普通短场通常只有一到三镜真需要预授权退路；把六镜都配上保底，等于交了第二份分镜，而读它的人分不出哪一镜才是真要紧的。两档不设中间值正是为此：它要求作者做一次取舍，不是给一个强度刻度。

本项不依赖任何平台品牌、版本或入口，只登记作者对本镜复杂度的判断。

## 制作段

```text
{id, shot_ids, opening_state, closing_state, prompt_context}
```

`shot_ids`按序拼接等于主镜头数组；段首末状态逐字等于首镜与末镜的**外层** `opening_state`／`end_state`——镜头有外层与 `execution` 两套状态，段状态对的是外层那套完整世界状态，不是执行层的精简版。相邻段终起态同样逐字相等。

**"逐字相等"指字符串严格相等，不做任何空白或标点归一化**：多一个句号、多一个尾部空格都算不一致。最省事的做法是把同一份状态文本从同一处取值，而不是两处手写。

`prompt_context`非空字符串，只含本段需要的空间、能力、资源与画外持续状态，使用名称而非内部ID，不写数字时码或全场未来结局。起终态位置/高度、动势、持物、持续术法/在途攻击、伤损与限制要能独立恢复，不使用“同上”。

执行稿自动选本段镜头`asset_ids`的并集，只打印资产名称、锚点与参考绑定（因此这些字段同样受时码与 ID 检查）；必要的画外施术者或器物应显式纳入对应镜头，而不是无条件输出全场资产。各段从0起的时码独立，不混全场时间。

## 关键帧

```text
{id, shot_id, time_sec, asset_ids, state, prompt, role}
```

`role` 必填，取 `single | prep | contact | result | handoff`。

引用有效镜头和资产；资产非空、无重复且属于该镜资产集合；时刻位于所属镜头闭区间。`state/prompt`非空，只写那一瞬间可见的姿态、接点、器物、光照、环境，不画完整动作链。

### 决胜接点三帧

每个`pivotal`节拍窗口内必须有`prep`、`contact`、`result`各至少一帧，且三者时刻严格递增。理由：决胜接触只给一张接触图，预备姿态和受力结果都没有静图可依，生成端只能自己编。其余镜头用`single`，不为凑数固定每镜帧数。

**三帧允许跨镜**：只要三个时刻都落在该 `pivotal` 节拍的窗口内，`prep` 在前一镜、`contact` 与 `result` 在后一镜是合法的——决胜接点本来常常横跨一次切镜。每帧仍各自归属它所在的那一镜，资产仍须是该镜资产的子集。

### 段界交接帧

每对相邻制作段的交接时刻必须有一张`role`为`handoff`的关键帧，时刻等于前段末镜终点，且**归属前段末镜**。

它要被当作前段末帧与后段首帧条件使用，所以：选段界时优先挑短暂稳定、轮廓可读的瞬间，不要停在"刚被贴住""刚接入"这类半动作上；`prompt`须是可独立复现的完整静图，不写内部ID。呼吸拍通常是最好的段界。

工具只检查每对相邻段的交接时刻至少有一张归属前段末镜的 `handoff` 帧；同一时刻另有其他帧（例如归属后段首镜的帧）是允许的。它也不禁止在非段界时刻另设 `handoff` 帧——有需要可以这么标，但那不替代段界那一张。姿态是否真的可复现、是否与前后镜自然衔接，属语义审阅。

## 代价账目

```text
cost: [{id, owner, item, from_beat, irreversible, consequence}]
```

非空数组。`owner`引用行动主体资产，`item`写支出的具体东西（符、器物缺口、伤处、暴露的位置、同伴的掩护），`from_beat`引用产生它的节拍，`irreversible`为布尔值，`consequence`写它此后限制什么具体动作。

**可查后果**：至少一项`irreversible`为真；`owner`至少两个不同主体。前者防止零代价取胜，后者防止代价只记在一方身上。

不可逆项是否真的在终态与之后每处引用中保留，属语义审阅。本字段不是灵力百分比或伤害数值表——它只登记"谁为这场付出了什么、此后不能再做什么"。

**没有赢家的结局同样适用。** "给赢的一方也记代价"是为了防止优势方分文未付，它不假定一定有赢家：双方都没达成目标时，两边的支出照样逐项登记，并各自指向新终态里一个仍在起作用的具体限制。此时胜负不再是收束这一场的东西，代价本身就是——谁此后不能再做什么，就是这一场留下的结果。

## 所知与实际

```text
knowledge?: [{id, holder, belief, truth, from_beat, cue, resolved_by?}]
```

有信息差时登记，无则整字段省略；登记则数组非空。`holder`引用行动主体资产，`belief`写该方的判断，`truth`写真实状态，`from_beat`引用建立误判的节拍，`cue`写观众可回溯的线索，可选`resolved_by`引用识破的节拍。

**可查后果**：`belief`与`truth`不得逐字相同；`resolved_by`不得等于`from_beat`，也不得早于它。

这是幻术、残影、神识、虚招和一切欺骗的记账处，让欺骗成为可登记的正面手段，而不只是禁令。主客观视角是否分明、识破线索是否真的先于识破出现，属语义审阅。

## 审阅及媒体观察

可选`review`必含：`{scope,fixed,pending,invalidated,verification}`，其中scope/verification非空字符串，fixed/pending/invalidated为字符串列表，可空。

可选子字段 `media_observations` 是数组，可空；每项严格 `{source,kind,observation,limitations}`，各字符串非空，kind为`image|video|audio`。记录作者实际依据及限制，不因为生成提示词就登记为已观察。

脚本始终只判定自身结构操作，语义状态为`needs_review`。作者登记的文本/媒体观察原样列出，不自动判通过。**没有观察时作者什么都不用填——`media_observations` 整字段省略或给空数组皆可，那句"未登记媒体观察"由渲染器自己打印**，不要在 JSON 里塞一条内容为"未登记"的假观察。渲染器不推断图片是否已生成、是否曾被查看；不再硬编码`not_generated`或“没有观看”。

完整交付需要实际审阅摘要；没有review时输出明确待补的骨架，不把它称为已完成语义审阅。

## 工具与输出

```bash
python scripts/combat_plan.py validate examples/01-sword-and-body.json
python scripts/combat_plan.py export examples/01-sword-and-body.json --out /path/to/new-directory
```

失败退出1、参数错误退出2；重复JSON键、非法常量、无效编码均拒绝。新目录导出前检查并在内存渲染，已有文件/目录不覆盖，失败清理本次临时产物。导出一律写 UTF-8 与 LF 换行，跨平台逐字节一致。

输出仍为七文件：`project.json`、`01-design.md`、`02-assets.md`、`03-storyboard.md`、`04-keyframes.md`、`05-video-prompts.md`、`06-review.md`。其中03是完整导演稿（含窗口规划），05是逐窗口精简执行稿；二者用途不同。有 `window_plan` 时05按窗口输出，每窗分直出稿与返修卡；04标窗口入口/出口帧；06增加窗口规划复核。

输出分配：代价账目与所知/实际进01；累积痕迹进02；节拍标记、光照、风险与保底构图、窗口规划进03；帧角色、窗口入口/出口帧进04；光照、保底构图、段界交接静图、直出稿与返修卡进05；代价、信息差、动作线、形态、特效、转场与窗口复核进06。执行稿仍不含内部ID、标记名、全场结局与非本窗口资产。

## 校验器查什么、不查什么

| 要求 | 结构可查 | 仍属语义审阅 |
| --- | --- | --- |
| 关键转折三帧 | 三种角色各至少一帧、时刻严格递增 | 预备姿态是否真的蓄力、结果是否真由该接触产生 |
| 呼吸拍 | 存在、不与转折重叠、不兼任转折 | 它是否真的让观众看清了什么 |
| 对手变招 | 存在、`requires`非空 | 变招理由是否来自他已察觉的信息 |
| 段界交接帧 | 每对相邻段的交接时刻至少有一张归属前段末镜（同刻其他帧允许） | 该姿态是否短暂稳定、是否可复现 |
| 光照归属 | 多镜方案全场不完全相同（单镜方案不触发）、字段非空 | 光束是否照亮了它经过的表面、转折处是否真的易手 |
| 战场痕迹 | 非空、字段齐、ID 唯一、`from_beat` 引用有效、至少一项先于最早转折结束 | 痕迹是否在后续镜头被尊重并限制路线 |
| 代价账目 | 非空、至少一项不可逆、至少两个归属、`owner` 是行动主体、`from_beat` 引用有效、`irreversible` 为布尔 | 不可逆项是否在终态与后续引用中保留 |
| 所知与实际 | 判断与真实不得逐字相同、`resolved_by` 不得等于也不得早于 `from_beat`、`holder` 是行动主体、两个拍引用有效 | 线索是否可回溯、主客观是否分明 |
| 生成风险 | `high`有非空保底、`low`不得有保底、取值受枚举约束、保底无时码 | 风险判断是否准确、保底构图是否真的更省 |
| 生成窗口 | 窗口连续覆盖全片、镜头交集正确、簇恰好同窗、内部边界有候选、C 级后窗高风险并带降级、入口出口帧对齐且内部共用 `handoff`、上限与簇跨度、形态不跨界、动作线切换有转场、跨界项进接缝包 | 簇是否真实、切点是否稳定、接缝包是否足够、长度是否由内容驱动 |
| 可复制文本洁净 | `execution` 六项文本、`cues[].text`、`prompt_context`、`fallback`、`keyframes[].prompt`、资产 `name`/`anchors`/`reference`、窗口状态/接缝包/窗口保底均不含阿拉伯数字时码，且不含任何已登记 ID | 文本是否真的可独立复制、是否漏掉了下一窗成立所需的信息 |

工具不判断空间可达、招式合理、动作耗时、观感、具体平台能力或模型服从程度。执行稿长度按真实需要控制，没有平台品牌通用的安全字数阈值；写平台专属请求前先确认版本、入口和模式。镜长是否等分、节奏是否有对比不作结构检查——那是导演判断，方法见 [spectacle-and-style.md](spectacle-and-style.md)，自检见 [review-and-repair.md](review-and-repair.md)。

## 生成窗口规划

`window_plan` 可选；本契约只接受 1.4。它是“按剧本关联定界、按能力取级”的登记，不是平台参数表。

```text
window_plan?: {
  capability: {max_window_sec?, source, arbitrary_start?, frame_conditioning?,
               internal_cuts?, audio?},
  knots: [{id, shot_ids, kind, why}],
  candidates: [{id, time_sec, shot_id, grade, reason, seam?}],
  windows: [{id, start, end, shot_ids, knot_ids,
             opening_state, closing_state, entry_frame, exit_frame,
             carries: {text, vfx?, forms?, costs?, knowledge?, tracks?, attrition?},
             fallback_splits, risk, fallback?}],
  notes?
}
```

- `capability.source`：`user_stated | verified | unknown`。`max_window_sec` 可省略；`unknown` 时不得写上限，用候选表给阶梯。上限是约束，不是规划起点。
- `knots`：真正会被拆坏的关联簇；每项 `shot_ids` 必须全部落在同一个窗口内。`kind` 取 `action | causal | information | form | space | scale | sound | performance | other`。
- `candidates`：切点候选；`grade` 取 `A | B | C`，X 类位置不登记。窗口内部边界必须引用一个候选；C 级边界由后窗承担风险（后窗 `high`，有 `fallback` 与非空 `fallback_splits`）。
- `windows`：按序连续覆盖全片，可跨镜头中部起止；`shot_ids` 必须是与窗口有正时长交集的全部镜头。窗口边界落在镜头中部时，必须对齐该镜 `execution.cues` 的某个 start/end，否则执行稿会切在半句动作上。相邻窗 `closing_state` 与 `opening_state` 在同一动作线内逐字相等；跨动作线边界须有世界内转场。
- `entry_frame`／`exit_frame`：时刻等于窗口起止；内部边界两侧共用同一张 `handoff` 帧；首窗入口、末窗出口可用 `single`。
- `carries`：`text` 必填，写下一窗不知道就会错的状态；`vfx`／`forms`／`costs`／`knowledge`／`tracks`／`attrition` 为已登记 ID 列表。边界前已开始或已发生的不可逆代价、仍有效的所知、激活的世界内特效、已开始形成或已形成的痕迹必须列入；动作线切换须列两条线。
- `risk`：`low | high`；高风险窗须写 `fallback` 与非空 `fallback_splits`，切完每段仍须在 `max_window_sec` 内。低风险窗不得写 `fallback`。
- `knots` 的跨度超过 `max_window_sec` 时直接报“改设计”，不静默拆。
- `vfx` 的 `post` 层特效不得跨窗口边界；跨界的 `world` 特效须进 `carries.vfx` 并在入口状态写阶段。
- 音频不新增字段：`capability.audio` 只声明生成端是否带音频，环境声、音乐状态、对白音色与声尾写进 `carries.text` 与执行稿声音栏。参考包不新增字段：用资产 `reference` 绑定与入口/出口帧表达；不给平台专属槽位名。
- 所有进入05的窗口文本（`opening_state`、`closing_state`、`carries.text`、`fallback`）与执行稿同样受检：不含阿拉伯数字时码，不含任何已登记 ID。`notes`、簇的 `why` 与候选的 `reason` 只进03，可写时码与 ID。

方法与写法见 [window-planning.md](window-planning.md)。

### 窗口输出分配

关联簇、切点候选、窗口、能力阶梯与判断记录进03；入口/出口帧进04；直出稿、返修卡与降级切点进05；窗口结构清单与复核进06。`segments` 仍是叙事与导出单位，不因 `window_plan` 取消。

## 分层字段

四个根字段全部可选，各自登记时须为非空数组。它们与已有对象共用全场唯一 ID 空间。四者里所有会进入可复制执行稿的文本（动作线名称与时间关系、特效名称与外观与各阶段、形态阶梯与 `shared_anchors`、转场的保留/改变/切点条件/遮挡物）与执行稿同样受检：不得含阿拉伯数字时码，不得含任何已登记 ID。

方法与写法见 [vfx-language.md](vfx-language.md)、[space-time-and-form.md](space-time-and-form.md)、[transitions.md](transitions.md)、[vfx-production.md](vfx-production.md)。

### 并行动作线

```text
tracks?: [{id, kind, name, time_relation}]       # kind: world | inner
beat.track / shot.track                          # 登记 tracks 后必填
shot.outer_state                                 # 内景镜头必填，世界线镜头禁止
```

用于识海、梦境、幻阵、入定等与外层同时进行的意识空间。成片仍是单条镜头时间轴，`tracks` 只声明每个节拍与镜头属于哪条线。

- 恰好一条 `world`，至少一条 `inner`。只有世界线时省略整个字段，单线战斗不需要动作线登记。
- 登记后每个节拍、每个镜头都要写 `track`；镜头引用的节拍须与镜头同线。外层在内景期间的变化不写成外层节拍，而写进内景镜头的 `outer_state`。
- `outer_state` 是同一时刻外层身体与世界的完整状态，与外层 `opening_state` 同格式，可写全场时码。**内景期间外界不暂停**。
- **状态连续按线检查**：每条线内相邻镜头的外层与 `execution` 终起态逐字相等；回到世界线的第一镜，外层 `opening_state` 须逐字等于最后一个内景镜头的 `outer_state`；它不与进入内景前那个世界线镜头的外层或 `execution` 终态比较，`execution.opening_state` 由作者按该 `outer_state` 另写精简版。不同线的镜头之间不要求终起态相等。
- 段界状态相等只在段界两侧属同一条线时检查；跨线段界靠上一条规则保证。
- 关键转折三帧只计同线镜头里的帧；呼吸拍只与同线的关键转折比较重叠。

### 签名特效

```text
vfx?: [{id, owner, name, layer, scale, function, look, lifecycle, spends, route, shot_ids, asset_id?}]
layer: world | post
scale: micro | body | field | heaven
route: one_pass | composite | asset
lifecycle: {release, omen?, travel?, contact?, result?, residue?, fade?}
```

- `owner` 引用资产（任何类型，环境效果可归属场景）。`shot_ids` 非空、无重复、引用有效镜头。
- `route` 为 `asset` 时 `asset_id` 必填且引用已登记资产；其余路线不得写 `asset_id`。
- `post` 层不进入世界：不得有 `contact` 与 `residue`。`world` 层须写 `residue` 或 `fade` 之一。
- `function`、`spends` 只进导演稿与审阅；执行稿逐项打印每个特效的 `name`、`look` 与已写的各生命周期阶段。

### 形态切换

```text
forms?: [{id, actor, from_asset, to_asset, beat_id, shot_ids, method, ladder,
          shared_anchors, cost_id, duration, exit}]
method: occlusion | morph | cut
```

- `actor` 为行动主体；`from_asset` 与 `to_asset` 是两套不同资产。
- `shared_anchors` 非空，每项须逐字出现在前后两套资产的 `anchors` 里。
- `beat_id` 须为 `pivotal` 节拍；`cost_id` 引用的代价须由 `actor` 本人支出。
- `ladder` 至少三级，通常为征兆、覆盖或切换、落定。
- `shot_ids` 中每镜须引用 `beat_id`，并同时登记前后两套资产。
- `morph` 连续形变时，涉及镜头全部须为 `high`。

### 转场

```text
transitions?: [{id, from_shot, to_shot, method, layer, keeps, changes, cut_condition, route, occluder?}]
method: occlusion | match_graphic | match_action | whip | eyeline | sound_bridge |
        medium_pass | cloud_pass | space_tear | ink_bleed | dissolve
route: cut | composite | bridge
```

- 硬切是默认，不登记；未登记的切点在分镜中一律视为硬切。
- `from_shot` 与 `to_shot` 须为相邻镜头；同一切点只登记一种转场。
- 全场转场数不超过 `2 × ceil(duration_sec / 30)`。
- 载体型方法（`occlusion`、`medium_pass`、`cloud_pass`、`space_tear`、`ink_bleed`）须写 `occluder`，其余方法不得写。
- `keeps`、`changes` 非空。
- `post` 层转场不得跨动作线，也不得位于同一形态切换的镜头之间。
- `route` 为 `bridge` 时两侧镜头都须为 `high`。

### 分层字段输出分配

动作线与形态切换进01；签名特效进02；镜头所属动作线、外层状态、特效与形态出现、带制作路线的转场进03；签名特效外观、形态阶梯、不含 ID 的转场说明进05；特效、形态、动作线与转场的结构清单进06。

| 要求 | 结构可查 | 仍属语义审阅 |
| --- | --- | --- |
| 并行动作线 | 一条世界线加至少一条内景线、全部拍与镜有归属、镜头与节拍同线、内景镜有外层状态、按线连续、回到世界线接上外层状态 | 外层危机在内景期间是否被记住、内景结果是否改变外层 |
| 签名特效 | 归属有效、层级与残留/接触相容、世界内特效有残留或消退、资产化路线有资产、镜头引用有效 | 外观是否跨镜一致、是否喧宾夺主、功能是否被看懂 |
| 形态切换 | 两套资产、共享锚点逐字存在、节拍为转折、代价归本人、阶梯至少三级、镜头含两套资产、连续形变为高风险 | 观众是否认出同一人、遮挡是否自然 |
| 转场 | 相邻、每切点一处、密度上限、载体与遮挡物对应、呈现层不跨线不入形态、桥接两侧高风险 | 转场是否必要、切点条件是否可执行 |
