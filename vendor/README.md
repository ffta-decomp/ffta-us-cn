# Immutable upstream source exports

`lock.json` records upstream URLs, exact revisions and SHA-256 for every exported
file. `fftadecomp` is the official public source/toolkit export, including the
merged generic extension interface and pinned compiler source with its GPL notices.
`rime-pinyin-simp` contains the selected dictionary and Apache-2.0 license.
The pinyin engine itself is maintained outside vendor in this project's engine/.

Do not edit dependency code. Needed changes belong in an upstream PR, followed
by an explicitly reviewed version update. `tools/verify_vendor.py` must pass
before and after builds. Compiler binaries, caches, generated headers and
fragments are external. Exports omit unrelated documentation/site assets.
No private-workflow documents, supplied ROMs, extracted game text or fonts are
included. Preserve upstream per-file copyright and license notices; a toolkit
metadata/documentation license does not override third-party source notices.
