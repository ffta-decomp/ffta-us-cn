# Plugin template

Fork this repository and maintain new plugins under `plugins/`. A single
`plugins/plugins.json` declares the plugins provided by this project. There is
no recursive dependency resolver or automatic scan of unrelated directories.

```text
ffta-us-cn/
  plugins.json                         # Host credits, CN base and optional overrides
  plugins/
    plugins.json                       # Local project declarations
    info/src/                          # Working native UI implementation
    info/tools/                        # Info build entry and renderer
    my_plugin/build.py                 # Your new plugin
  examples/plugin-template/            # Minimal entry and declaration to copy
  config/plugin-projects.json           # Local project and optional pinned Git sources
  config/plugin-projects.lock.json      # Declared source hashes
  vendor/plugins/<project>/<hash>/      # External Git exports only
  engine/                              # Existing CN/native naming implementation
```

## Add a local plugin

Copy `examples/plugin-template/build.py` to `plugins/my_plugin/build.py` and
append the object in `examples/plugin-template/declaration.json` to the
`plugins` array in `plugins/plugins.json`:

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "content": "My plugin description\nAuthor name",
  "enabled": true,
  "priority": 0,
  "entry": "my_plugin/build.py",
  "files": ["my_plugin/build.py"]
}
```

Run `python3 tools/plugin_projects.py sync` and review the updated lock. Build
with the usual explicit private inputs. Local entries are loaded directly from
`plugins/`, without copying to `vendor/`. Sync after editing declared sources;
verification catches stale hashes. No root registration or build-driver edit
is required. Commit the declared sources, manifest and updated lock together.
The starter is deliberately a no-op until its extension manifest is implemented.

Set `enabled` to `false` to disable an entry. Optional `feature` ties it to an
existing build feature (`cjk`, `link_fix`, `info`, `italic_font`); otherwise it
runs whenever enabled, including English and exact-reference profiles. Disable
your custom changes when reproducing the original ROM. The Info sidebar shows
enabled plugin credits and currently supports at most four pages.

## Build entry

Additional plugins export this Python function:

```python
def prepare(reference, image, args, output, config):
    # Generate sources/assets under output and construct a pinned manifest.
    return manifest_path, report
```

`reference` is authenticated US ROM bytes; `image` is the current ROM after
CN, pinyin, link, font and Info stages. `args` contains build options, `output`
is a new external directory, and `config` contains pinned decomp module
metadata. Return a `build-extension-v1` manifest and JSON-compatible report.
See the starter and the official vendored `tools/build_extensions.py` for
source replacements and classified code/data/resource fragments. All inputs
must have pinned hashes; original-range hashes refer to `reference`.

Plugins run in ascending `(priority, id)` order. Conflicting byte changes by
additional plugins fail; priority does not silently authorize overwriting one
another. Info retains its specialized font/UI build stage. `uscn` owns the
original font with priority 1000; append styles cannot replace its cells or
codes. Font rules are described in [font extensions](font-plugins.md).

The root `plugins.json` can override exported defaults with an explicit
`{"id": "my_plugin", "project": "builtin", "enabled": false}` registration.
Use `--disable-info` to disable the specialized built-in Info UI stage.

## External plugin projects

The default project registry reads local source:

```json
{"id": "builtin", "source": {"kind": "builtin", "path": "plugins"}}
```

Optionally add an external project with its actual URL and complete commit SHA:

```json
{"id": "external", "source": {"kind": "git", "url": "https://example.invalid/plugin-project.git", "revision": "<complete immutable commit SHA>"}}
```

The external repository has the same `plugins.json` declaration contract at its
root and may export multiple plugins. `sync` fetches only when explicitly run,
imports the manifest and union of declared file lists into `vendor/plugins/`,
and removes its temporary checkout. Builds are offline and verify source
hashes. Never edit imported snapshots. Source archives include locked exports.

Projects may maintain their own `vendor/`, tests and tools. These are not
exported unless explicitly declared. Paths escaping the project and private
ROM/font/patch resources are rejected. There is no transitive plugin-project
resolution. Exported IDs must be unique across projects. Python helpers use
relative imports and must appear in `files`.
