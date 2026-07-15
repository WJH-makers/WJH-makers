# Profile 自动化设计

解决：**每新建/推送一个仓库，不必再手改个人主页 README。**

## 架构

```text
┌─────────────────────┐     API 列表公开仓库      ┌──────────────────────┐
│  你的公开仓库们        │ ──────────────────────► │ generate_profile_    │
│  description/topics │                           │ readme.py            │
└─────────────────────┘                           └──────────┬───────────┘
                                                             │
┌─────────────────────┐     精选/排除/文案覆盖                 │ 写入 AUTO 区块
│ config/profile.yml  │ ─────────────────────────────────────┤
└─────────────────────┘                                      ▼
                                                    ┌──────────────────┐
                                                    │ README.md        │
                                                    │ (静态文案 + AUTO) │
                                                    └──────────────────┘
                                                             ▲
┌─────────────────────┐     schedule / dispatch / 改 config   │
│ Actions:            │ ─────────────────────────────────────┘
│ sync-profile.yml    │
└─────────────────────┘
```

| 层 | 谁改 | 改什么 |
|----|------|--------|
| **仓库元数据** | 建库时 | `description` · `topics` · `homepage` |
| **策展配置** | 偶尔 | `config/profile.yml`（exclude / featured / overrides） |
| **自我介绍** | 很少 | README 静态段落（关于我、经验地图、技术栈） |
| **项目表/最近动态** | **机器人** | `<!-- AUTO:* -->` 区块，禁止手改（会被覆盖） |

## 本地命令

```bash
cd WJH-makers   # 本仓库
pip install -r scripts/requirements.txt
python scripts/generate_profile_readme.py          # 生成并写 README
python scripts/generate_profile_readme.py --check  # CI：是否过期
python scripts/generate_profile_readme.py --dry-run
```

## 何时自动跑

| 触发 | 说明 |
|------|------|
| **每 6 小时** | `cron` 扫公开仓库 |
| **手动** | Actions → Sync Profile README → Run workflow |
| **改配置/脚本** | push 到 `config/` 或 `scripts/generate_*` |
| **repository_dispatch** | 其他仓库/脚本可远程踢一脚 |

手动立即同步：

```bash
gh workflow run sync-profile.yml -R WJH-makers/WJH-makers
```

从任意仓库触发（需有 `repo` 权限的 token）：

```bash
gh api repos/WJH-makers/WJH-makers/dispatches \
  -f event_type=sync-profile
```

## 新仓库 checklist（只需这一步）

1. 创建 **public** 仓库（fork 不会进表）。
2. 写一句清楚的 **Description**（中文或英文均可）。
3. 加 **Topics**（如 `nextjs` `java` `compiler`）→ 会进「技术」列。
4. 若有线上地址，填 **Website**（homepage）→ 表内显示 site 链接。
5. （可选）若 description 太烂、又不想改仓库设置 → 在 `config/profile.yml` 的 `overrides` 写 skill/description。
6. （可选）想置顶 → 把名字加进 `featured`。
7. （可选）不想展示 → 加进 `exclude`。
8. 等最多 6 小时，或跑一次 `gh workflow run sync-profile.yml`。

## 不要做的事

- 不要手改 `<!-- AUTO:PROJECTS:START -->` … `END` 之间的表格（下次同步会被覆盖）。
- 不要在公开 README 写密钥、内网 IP、隧道说明。
- 不要把相册/作业克隆仓放进 featured；用 `exclude`。

## 与现有自动化的关系

| Workflow | 作用 | 是否改 README 文案 |
|----------|------|-------------------|
| **sync-profile** | 仓库表 + 最近动态 | ✅ AUTO 区块 |
| profile-3d | 3D 贡献图 SVG | ❌ 只改 `profile-3d-contrib/` |
| snake | 贪吃蛇 SVG → `output` 分支 | ❌ |
| readme-health | 检查链接/标记 | 只读 |

## 设计原则

1. **单一事实来源**：项目长什么样，以各仓库 Settings 为准。  
2. **策展与数据分离**：排序/黑名单/话术润色进 yml，不写死在 HTML 表。  
3. **徽章已动态**：Public Repos 数量用 shields dynamic JSON，无需手改数字。  
4. **失败可重试**：生成失败不糊乱表；本地 `--check` 可测漂移。
