# 微信本地读取 Skill

[English](README.md) | [简体中文](README.zh-CN.md)

读取已获授权的 Windows 微信聊天记录，以及本地缓存的图片、语音、视频和文件。智能体可通过本地命令行工具查找会话并读取内容。

## 安装

将本目录放入所用智能体的 skill 目录。Codex 用户可放入 `~/.codex/skills/wechat-local-read`，然后开启新会话加载此 skill。

使用 64 位 Windows Python，在 skill 目录中安装依赖：

```text
python -m pip install -r requirements.txt
```

运行状态、数据库密钥、聊天导出和提取的媒体应保存在 skill 目录之外的私人目录中。

## 使用

启动微信并登录账号后，检查读取状态、查找会话并读取消息：

```text
python scripts/read_wechat.py --state-dir C:\private-wechat-state status
python scripts/read_wechat.py --state-dir C:\private-wechat-state find "群聊名称"
python scripts/read_wechat.py --state-dir C:\private-wechat-state messages --chat CHAT_ID --limit 50 --offset 0
```

将 `CHAT_ID` 替换为 `find` 返回的聊天 ID。电脑存在多个账号时，通过 `--account ACCOUNT_DIRECTORY_NAME` 指定账号目录名。

结果以 UTF-8 JSON 输出，消息按时间从新到旧排列。使用返回的 `next_offset` 继续读取。关键词和时间条件只筛选当前分页；新消息到达时，可重叠读取并按 `(shard, local_id)` 去重，减少遗漏。

## 媒体支持

| 类型 | 功能 |
| --- | --- |
| 图片 | 读取本地缓存图片，包括支持的 WXGF 图片。可通过 `--tier best`、`original`、`mid` 或 `thumb` 选择副本。 |
| 语音 | 提取 SILK 音频。解码和转写需要单独的工具。 |
| 视频 | 提取本地缓存的视频文件。 |
| 文件 | 按文件名查找本地候选，拒绝重复匹配。候选标记为 `identity_verified: false`，使用前须确认它与目标消息的对应关系。 |

媒体命令需要消息的 `shard` 和 `local_id`，具体参数见 [SKILL.md](SKILL.md)。缺失的媒体需要先在微信中打开或下载。首次读取图片可能需要在微信中打开一张图片，使图片密钥可供读取。图片分辨率取决于缓存副本。

兼容性取决于微信版本和可用的本地数据。文件提取仍属于实验性功能。

## 文档与许可证

- [SKILL.md](SKILL.md)：智能体操作说明和命令参考。
- [THIRD_PARTY.md](THIRD_PARTY.md)：依赖来源和许可证说明。
- [LICENSE](LICENSE)：Apache-2.0 许可证。

数据库与媒体处理后端基于 [wechatauto-replica v1.2.6](https://github.com/fanyuantaier/wechatauto-replica/tree/v1.2.6)。
