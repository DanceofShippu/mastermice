# Mouse Colony Manager v26.1.0

实验小鼠群体管理命令行工具（CLI）。单文件 SQLite 数据库 + 事件日志（event-log）架构：每一次变更（新建、性别、处死、寄出……）都会在 `events` 表留下一条带日期的事件记录，形成每只小鼠的完整历史。

查询工作请使用 **DB Browser for SQLite** 直接打开数据库（见下文），CLI 专注录入与更新。

## 功能

- **新建小鼠**：单只 / 批量（逗号分隔 ID 与字段值，值不够时自动用最后一个值向后填充）
- **更新小鼠**：单只（管理菜单逐字段更新）/ 批量更新，全部字段 + 特殊字段（multi-checks、notes）
- **状态管理**：`alive` / `sacrificed` / `died due to accident` / `sent out`（批量处死 = status 填 `sacrificed`）
- **git 式提交流程**：先收集（暂存）→ 审查（diff）→ 确认 → 单事务写入，出错整批回滚
- **录入中途可退出**：任何输入处 `!c` 取消整个操作，`!r` 重输当前字段；审查时可 `r` 全部重填
- **ID 大小写敏感**：`GYP1` 与 `gyp1` 是两只不同的鼠（主键语义）
- **日期智能提示**：显示年龄（P 天数）与里程碑（P7/P21/P42 未来节点）
- **数据校验**：日期格式与未来日期、gender、status 非法值直接拦截并重输

## 环境要求

- Python 3（仅用标准库，无第三方依赖）
- SQLite 数据库文件 `micecolony.db`（首次运行自动创建于脚本同目录）

## 使用方法

```bash
python3 main.py
```

```
    (\___/)
    (='.'=)
    (")_(")~

=== Mouse Colony Manager v26.1.0 ===
(1) Update
(q) Quit
> 
```

主菜单下直接输入某只小鼠的 ID（大小写敏感）可快速进入它的管理界面。

### 管理小鼠菜单

```
1. update gender        5. update strain        9. update multi-checks
2. update dob           6. update father id    10. edit/clear notes
3. update location      7. update mother id    11. back to main menu
4. update genotype      8. update status
```

### 输入约定

| 输入 | 含义 |
|---|---|
| 直接回车（空输入） | 跳过该字段（更新 = 保持不变） |
| `!c` | cancel：取消整个操作，不写入任何内容 |
| `!r` | redo：重新输入当前字段 |
| `y` / `n` / `r` | 审查时：提交 / 放弃 / 全部重填 |

批量模式还支持 `short -> pad last`：值比 ID 少时，余下小鼠沿用最后一个值。
例如批量处死 3 只鼠：IDs 填 `A1,A2,A3`，status 只填一个 `sacrificed` 即可。

### git 式审查示例

```
--- Review: 2 mouse(es) to update ---
~ GYP17664: dob: 2026-02-17 -> 2026-09-01
~ GYP16718: dob: 2025-12-22 -> 2026-09-01
Apply? (y)es / (n)o / (r)estart entry:
```

## 数据模型

`micecolony.db` 位于脚本同目录，两张表：

| 表 | 说明 |
|---|---|
| `mice` | 小鼠档案：`mouse_id`(主键)、gender、dob、location、genotype、strain、father_id、mother_id、status、multi_checks、notes |
| `events` | 事件日志：`mouse_id`、`event_type`、`event_value`、`event_date`，如 `birth / born`、`status / sent out` |

用 DB Browser for SQLite 打开 `micecolony.db` 即可查询、导出；CLI 与 GUI 同时操作同一文件时注意先后提交。

## 版本记录

**26.1.0**
- 单条模式所有输入提示补充 `empty to skip` / `required` 说明，与批量模式对齐
- 状态新增 `sent out`（寄出）
- 批量更新支持向后填充（`short -> pad last`），与批量新建一致
- git 式流程：录入后先审查（diff）再确认提交；`!c` 取消 / `!r` 重输 / 审查 `r` 全部重填
- 批量更新字段校验补全（dob/gender），坏值重输不再整批中止
- 界面统一左对齐；主菜单显示版本号

## 仓库约定

- `micecolony.db` 为本地数据文件，不入库（见 `.gitignore`）
- 远程仓库：`github.com/DanceofShippu/mister`
