# Builtin plugin project

This is a plugin source project, currently exporting `info`. Add another entry
to this project's `plugins.json` to provide another plugin from the same project.
Each entry lists its Python build entry and every source/notice file to export.

Develop and test in this directory. A project's own `vendor/`, tests and other
development files stay here unless explicitly listed in the export manifest.
The host does not resolve this project's dependencies or copy its whole tree.
Any required standalone implementation must be included in the declared export.

The Info build entry consumes the template's host-v1 services (`plugin_info`,
native source-extension compilation, glyph mapping and font generation). It
returns an upstream build-extension manifest through `prepare(...)`. The
`tools/build_plugin_info.py` host adapter loads this entry from the verified
snapshot, never from the authoring directory.

Run `python3 tools/plugin_projects.py sync` at the template root after changing
exported sources. Review `config/plugin-projects.lock.json` with those changes.
Never edit `vendor/plugins/` snapshots. Git consumers can instead pin a complete
commit of a project having this same `plugins.json` contract at its root.
