# Provenance

This skill's local CLI and instructions were written for the Windows read-only workflow. It is not a fork of an upstream MCP tool: the earlier MCP `server.py` was a local wrapper around the database backend.

The vendored `scripts/vendor/db.py` and `scripts/vendor/media.py` come from [fanyuantaier/wechatauto-replica v1.2.6](https://github.com/fanyuantaier/wechatauto-replica/tree/v1.2.6), licensed under Apache-2.0; the complete license is retained at `scripts/vendor/LICENSE`. Both files were matched by full text comparison to tag v1.2.6 on 2026-10-10 (db.py differs only in line endings). The database file was retained from the earlier local reader; the media file was downloaded from upstream main on 2026-10-10 and then matched to that release.

The vendored files are retained without edits. Read-only operation is enforced by the narrow CLI entrypoints, logger stub, runtime process detection override, and avoidance of the upstream UI/sending entrypoints. The upstream repository contains broader automation functions; this skill does not invoke those.

No NOTICE file was present in the inspected upstream root. Preserve applicable upstream notices if updating the dependency. Publish source and synthetic tests only; private keys, databases, attachments, chat names, identifiers and logs are not repository content.
