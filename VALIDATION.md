# Validation snapshot — 2026-10-10

Windows, 64-bit Python, logged-in WeChat. These are local-account observations, not a guarantee for every WeChat version or machine.

## Passed

- Original reader matrix: 10/10 checks. Two authorized chats, three 20-record pages each, no duplicate `(shard, local_id)` identities, ordering/offset violations, or filter discrepancies.
- Local history pagination reached the end of the available local records: 333 and 192 messages, using 100-record pages with a maximum of 20 pages per chat. No duplicate or ordering violations in the tested snapshot.
- Standalone CLI matrix: 12/12 checks, including discovery, two pages per chat, image status, original/thumbnail extraction, and cached extraction in a later fresh reader process.
- Images were fully loaded with Pillow: original/thumbnail dimensions 674x848 / 144x180 and 2880x1656 / 180x104.
- Ten synthetic regression tests cover account/cache scoping, multiple-account selection, rejection of shard errors, account path validation, compound file-type recognition, exposed command scope, V2 encrypted PNG decoding, thumbnail fallback, output path containment, and rejection of ambiguous filenames.
- Two simultaneous status commands succeeded with serialized cache access.
- A one-second worker timeout returned a bounded error. A later read succeeded, demonstrating lock release after worker termination.
- A newly user-sent file-transfer-assistant text was absent from the baseline and visible on subsequent reads. No end-to-end latency guarantee was measured.
- Skill metadata passed the Skill Creator validator.
- User confirmed a full WeChat restart; a fresh reader still read the new test text successfully.
- Real decrypted WXGF/HEVC pictures in both authorized chats converted to fully loadable JPEG at 1080x2376 and 1280x1358. A fresh reader decoded a cached WXGF picture again after WeChat restart.
- Twelve additional groups yielded 2,320 recent messages without a read failure. This is a bounded recent-history sample.
- Two real voice samples from one additional group extracted as SILK, passed header checks, and decoded using separately installed `pilk` 0.2.4 into nonempty 16-bit mono 24 kHz PCM/WAV. Durations were 6.98 and 4.34 seconds. No transcription was attempted.
- A bounded older-media query in the same twelve groups examined 707 video rows and 62 ordinary-file rows, finding 117 and 3 local filename matches respectively. This discovery count is separate from payload decoding tests.
- Two videos from different groups extracted and decoded fully with PyAV: 350/161 frames, 11.633/5.336 seconds, 576x1280/544x960. Copied payloads matched their local sources byte for byte.
- Three unique PDF filename candidates extracted and matched their local sources byte for byte; header/trailer checks, PyMuPDF parsing, and in-memory rendering of all 12/55/88 pages passed. These checks establish copy fidelity and format, while attachment identity remains explicitly unverified.
- A video without a local cache returned unavailable and produced no bogus payload.
- Independent review identified account switching, cache scope, cross-shard image output collisions, hidden partial reads, availability semantics and codec dependency gaps; local CLI corrections were implemented. Output directories now include account and shard.

## Pending / outside current verified scope

- A new machine with no cached database/image keys; changed WeChat versions, permission mismatch, real multiple-account data and very large histories.
- Continuous real-time monitoring or a quantified latency bound. Offset pages can shift during incoming traffic; deduplicate and overlap reads.
- Actual corrupt message shards; rejection is tested synthetically, without damaging user databases.
- Codec-child cleanup during an actual transcoding timeout.
- Missing-original / thumbnail-only real messages. The CLI distinguishes tiers, but both tested real messages had all three copies.
- Recent additional-group samples contained 42 video messages with no matching local payloads and 282 type-49 cards/links/replies, all with appmsg subtypes other than ordinary file subtype 6. Absence of a local payload is not a codec test.
- The experimental file resolver uses message-resource filenames, rejects duplicate matches, and labels candidate identity unverified. A sole matching filename alone cannot prove attachment identity.

The tested environment supports local text/history, cached images, SILK extraction with separate voice decoding, and the two tested MP4 videos. File extraction remains an experimental candidate resolver with unverified message identity. The remaining cases above are outside this validation snapshot.
