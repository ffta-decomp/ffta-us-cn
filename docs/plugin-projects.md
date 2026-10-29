# Plugin project layout

The Chinese project is the template host. A plugin project may provide several
plugins through one `plugins.json` export manifest. There is no recursive
dependency resolver: the plugin project owns its own dependencies and tests.
Only declared files cross the project boundary.

```text
ffta-us-cn/
  plugins.json                         # Enabled plugin metadata, font rules, priority
  config/plugin-projects.json           # Project sources: builtin directory or Git commit
  config/plugin-projects.lock.json      # Exported files and their hashes
  plugins/builtin/                      # Bundled project, editable canonical sources
    plugins.json                       # Declares one or more exported plugins
    info/src/                          # Info implementation
    info/tools/                        # Info build entry and host renderer
    vendor/                            # Optional project-private dependencies, not auto-exported
    tests/                             # Optional project-private tests, not auto-exported
  vendor/plugins/<project>/<hash>/      # Imported, immutable declared source files
  tools/                               # Template build/import services
  engine/                              # Existing CN/native naming implementation
```

A plugin project's manifest has explicit file names, relative to that project:

```json
{
  "schema": 1,
  "plugins": [
    {"id": "info", "entry": "info/build.py", "files": ["info/build.py", "info/ui.c", "info/ui.h", "NOTICE.md"]},
    {"id": "another", "entry": "another/build.py", "files": ["another/build.py", "another/patch.c", "NOTICE.md"]}
  ]
}
```

The importer copies this manifest and the union of those file lists. It never
copies an entire checkout or automatically follows another project's dependency
configuration. A project may use its own `vendor/`, tests and development tools;
if the exported plugin needs a helper source or notice, list that file explicitly.
Paths escaping the project and private ROM/font/patch resources are rejected.

Each declaration may also supply `feature`, `name`, `content`, `priority` and
`font` defaults. The host registers it with `{"id": "info", "project": "builtin"}`
in its own `plugins.json`; explicit host fields override those defaults. Info's
font rules and credits therefore travel with its exported project manifest,
while the CN base and its highest priority remain controlled by the template.

The host source registry selects either source kind:

```json
{"id": "builtin", "source": {"kind": "builtin", "path": "plugins/builtin"}}
```

```json
{"id": "external", "source": {"kind": "git", "url": "https://example.invalid/plugin-project.git", "revision": "<complete immutable commit SHA>"}}
```

Use the actual repository URL and complete commit SHA for Git sources. Import
with `python3 tools/plugin_projects.py sync` and review the updated lock file.
The command fetches Git sources only when explicitly invoked, exports declared
files to `vendor/plugins/`, and removes its temporary checkout. Internal files
not declared in the manifest neither enter the lock nor get packaged.

Builds verify locked snapshots and may restore missing builtin snapshots from
identical bundled source. Changed builtin exports require an explicit sync;
Git snapshots must already have been synced. Never edit an imported snapshot.
`tools/plugin_projects.py verify` checks imports without fetching. Source
packages contain the locked exports so Git plugins can build offline.

`load_entry(plugin_id)` loads the declared Python entry from its snapshot.
Exported IDs must be unambiguous across referenced projects. Info's host adapter
calls its `prepare(...)` entry to produce the official decomp extension manifest.
This is source selection, not a runtime plugin loader.

The host's `plugins.json` owns display credits and font priorities. `uscn` has
priority 1000 and owns base glyphs/codes. The `info` plugin has priority 100;
its optional italic style appends new glyphs and emits updated character tables.
There is no separate `italic` plugin. See [font rules](font-plugins.md).
