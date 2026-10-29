# Local plugins

Fork this repository and add your plugins here. `info/` is the working native
UI example. `../examples/plugin-template/` contains a minimal build entry.

1. Copy `examples/plugin-template/build.py` to `plugins/my_plugin/build.py`.
2. Add the object from `examples/plugin-template/declaration.json` to the
   `plugins` array in this directory's `plugins.json`.
3. Run `python3 tools/plugin_projects.py sync`, review the lock, then build as
   usual. No root catalogue registration or build-driver edits are needed.

Local sources are compiled directly here, without a `vendor/` copy. After
changing declared sources, sync again to record their hashes. Set `enabled` to
`false` to disable a plugin. The starter returns an empty extension manifest;
replace it with actual source replacements or resource/pointer fragments.

Declare all source/helper/notice files used by the plugin. An external consumer
imports only these files and `plugins.json`. Project-private `vendor/` and tests
are not automatically exported. Keep private game resources outside the repo.

See [the plugin contract](../docs/plugin-projects.md) for build-entry arguments,
external Git imports, metadata overrides and font priorities.
