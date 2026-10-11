# WeChat Local Read skill

[English](README.md) | [简体中文](README.zh-CN.md)

Read authorized Windows WeChat chat history and locally cached images, voice messages, videos, and files. This skill provides a local CLI for agents to find conversations and retrieve their contents.

## Installation

Place this folder in your agent's skill directory. For Codex, use `~/.codex/skills/wechat-local-read`, then start a new session to load the skill.

Use 64-bit Windows Python and install the dependencies from the skill folder:

```text
python -m pip install -r requirements.txt
```

Keep runtime state, database keys, chat exports, and extracted media in a private directory outside the skill folder.

## Usage

With WeChat running and your account logged in, check availability, find a conversation, and read its messages:

```text
python scripts/read_wechat.py --state-dir C:\private-wechat-state status
python scripts/read_wechat.py --state-dir C:\private-wechat-state find "Your group name"
python scripts/read_wechat.py --state-dir C:\private-wechat-state messages --chat CHAT_ID --limit 50 --offset 0
```

Replace `CHAT_ID` with the ID returned by `find`. If the computer has multiple accounts, specify the account directory name with `--account ACCOUNT_DIRECTORY_NAME`.

Results are UTF-8 JSON. Messages are returned newest first; use `next_offset` to continue reading. Keyword and time filters apply to the current page. When new messages arrive, overlapping pages and deduplication by `(shard, local_id)` help avoid omissions.

## Media support

| Media | Behavior |
| --- | --- |
| Images | Reads local cached images, including supported WXGF images. Select a copy with `--tier best`, `original`, `mid`, or `thumb`. |
| Voice | Extracts SILK audio. Decoding and transcription require separate tools. |
| Video | Extracts locally cached video files. |
| Files | Finds local candidates by filename. Duplicate matches are rejected. Candidates carry `identity_verified: false`; confirm their association with the requested message before using them. |

Media commands require the message's `shard` and `local_id`; see [SKILL.md](SKILL.md) for command details. Missing media must first be opened or downloaded in WeChat. The first image read may require opening a picture in WeChat to make its image key available. Image resolution depends on the cached copy.

Compatibility depends on the WeChat version and available local data. File retrieval remains experimental.

## Documentation and license

- [SKILL.md](SKILL.md): agent instructions and command reference.
- [THIRD_PARTY.md](THIRD_PARTY.md): dependency attribution and licenses.
- [LICENSE](LICENSE): Apache-2.0 license.

The database and media backend is derived from [wechatauto-replica v1.2.6](https://github.com/fanyuantaier/wechatauto-replica/tree/v1.2.6).
