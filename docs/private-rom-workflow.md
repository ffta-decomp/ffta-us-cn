# User build: one root file and a separate private ROM repository

The organization's template holds generic source. A user's source fork holds
their plugins and `rom-source.txt`. The independent private ROM repository holds
the game inputs. Never put ROMs in either source repository.

## Configure your personal fork

Copy `rom-source.example.txt` to `rom-source.txt` in your fork's root and replace
its single line with your private ROM Git URL:

```text
https://github.com/YOUR_USER/ffta-roms.git
```

SSH form (`git@github.com:YOUR_USER/ffta-roms.git`) also works. Commit this file
only in your personal fork. Do not put tokens, passwords, extra JSON fields or
machine paths in it. The organization's template has only the example file;
without the actual root file its manual ROM build is skipped.

There are no Actions variables for repository address, input revision or an
enable switch. The checkout's actual input commit is recorded in the build
report. Complete ROM SHA-256 pins still determine the supported versions.

## Local build

Use your existing Git authentication for the private repository. After cloning
the source and creating `rom-source.txt`, run:

```sh
python3 tools/ci_private_build.py \
  --work-dir ../private-build --publish-dir ../patches --profile default
```

Use new directories outside the source checkout. The entry fetches public Git
dependencies at locked revisions, clones the configured private repository into
the external work directory, identifies the ROMs by hash, imports resources,
bootstraps the compiler and builds. Python, Git, Clang, Make and ARM binutils are
required. No external font/OCR/spreadsheet/Swift runtime is needed.

For an existing explicitly selected input checkout, `--rom-dir ../private-roms`
avoids another clone. The older `--rom-archive` remains a compatibility option.
No other local directories or game files are automatically discovered.

## Manual Actions build

Actions also reads the root file. Open Actions in your source fork, select
**Private ROM build (manual opt-in)**, and choose **Run workflow**. There are no
push, pull-request or scheduled builds. Only the build profile is selectable.

Private repository access still needs authentication. Add a read-only deploy
key on the ROM repository and store its private half in the source fork's
`PRIVATE_ROM_SSH_KEY` Actions secret. This is the only Actions setting required;
the source fork's default token cannot read a different private repository.
Local builds instead use normal Git authentication. No personal access token
or organization-wide credential is needed.

The workflow checks out source and private inputs into sibling directories.
Only the IPS and hash report are uploaded as seven-day artifacts. An `always()`
cleanup removes private inputs and generated resources. The organization template
contains no user's real input URL, deploy key or ROMs.

## ROM files and identity

Prefer two plain files in the private input repository's root:

```text
ffta-us.gba
ffta-us-cn-v1.1.gba
```

Names are descriptive labels; complete SHA-256 determines each role. Duplicate,
missing, wrong-version and wrong-size inputs fail. Original native glyphs and
widths are checked against the owner-provided character table.

| Role | Required SHA-256 |
| --- | --- |
| US retail | `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19` |
| US Chinese v1.1 | `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03` |

Existing private repositories with `inputs.zip` remain readable when no direct
ROM files are present. ZIP is not required for new repositories; member paths
are never extracted, and the legacy archive limits remain 64 MiB/64 members.

`default` builds CN/pinyin/link/Info/italic and enabled custom plugins.
`exact-reference` disables optional built-in changes and requires byte identity
with the CN reference; disable any custom plugins that change the output.
