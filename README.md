# WeChat Local Read skill

Read authorized Windows WeChat text history and locally cached media through a standalone CLI. The database and media backend is derived from [wechatauto-replica v1.2.6](https://github.com/fanyuantaier/wechatauto-replica/tree/v1.2.6), under Apache-2.0.

## Setup

Use 64-bit Windows Python and install `requirements.txt` in that environment. Place this folder in your agent's skill directory when ready to install. Keep private state and decoded images outside this folder.

```text
python -m pip install -r requirements.txt
python scripts/read_wechat.py --state-dir C:\private-wechat-state status
python scripts/read_wechat.py --state-dir C:\private-wechat-state find "Your group name"
```

On multiple-account machines specify `--account ACCOUNT_DIRECTORY_NAME`. A first image read may require opening a picture in WeChat so its dedicated key is available. Missing local images cannot be fetched by this read-only CLI.

The script emits UTF-8 JSON, uses fresh worker processes and a bounded cache lock, isolates accounts and image shards, and provides no sending command. Keyword and time filters apply to a scanned page; they do not independently search all history.

See [SKILL.md](SKILL.md) for agent instructions, [VALIDATION.md](VALIDATION.md) for what has and has not passed, and [THIRD_PARTY.md](THIRD_PARTY.md) for provenance. Run synthetic tests with `python scripts/test_reader.py`.

Voice extraction produces SILK; separate decoding was tested with optional `pilk` 0.2.4. Video/file extraction is experimental. File candidates are labeled `identity_verified: false`: a unique filename alone does not establish that the payload belongs to the requested message. Confirm its identity before summarizing it. The CLI rejects duplicate filename matches.

## Publishing

Publish this source folder only, never your runtime state, database keys, chat exports or actual chat images. Retain the Apache-2.0 license and upstream attribution. Skill-layer behavior belongs in this repository; reproducible library defects can be reported to upstream with minimal synthetic examples.

The former local MCP wrapper's FileExistsError was not reproduced in the fresh-process tests. Its cause remains unresolved; do not present it as a confirmed upstream defect.
