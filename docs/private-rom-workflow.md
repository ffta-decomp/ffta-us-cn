# User build: public source and a separate private ROM repository

Keep three roles separate:

- The organization's public template contains generic source, manifests and locks.
- A user's source clone contains their plugins and repository-specific Actions
  settings. It never contains ROMs or private input archives.
- The user's independent private ROM repository contains `inputs.zip` and its
  provenance README. It does not contain template source or build outputs.

## Fresh local build

Clone the template, fetch public dependencies, and clone your own private ROM
repository into a sibling directory. Substitute your real repository URLs:

```sh
git clone https://github.com/ORGANIZATION/ffta-us-cn.git source
cd source
python3 tools/fetch_dependencies.py
python3 tools/verify_vendor.py
cd ..
git clone git@github.com:USER/ffta-roms.git private-roms
cd source
python3 tools/ci_private_build.py \
  --rom-archive ../private-roms/inputs.zip \
  --work-dir ../private-build --publish-dir ../patches --profile default
```

Use new external output directories. The entry imports resources, recovers the
build map from the committed owner-provided native table, bootstraps the compiler
and builds the selected profile. Python, Git, Clang, Make and ARM binutils are
required; no spreadsheet/OCR/Swift runtime is needed.

## Manual Actions workflow in the user's source clone

The template's workflow has only `workflow_dispatch`; push, pull requests and
schedules never trigger it. Its job is skipped unless `ENABLE_PRIVATE_ROM_BUILD`
is `true`. Configure these settings in your own source clone, not the template:

| Setting | Value |
| --- | --- |
| Variable `ENABLE_PRIVATE_ROM_BUILD` | `true` |
| Variable `PRIVATE_ROM_REPOSITORY` | `USER/ffta-roms` |
| Variable `PRIVATE_ROM_REVISION` | Complete 40-character input repository commit |
| Secret `PRIVATE_ROM_SSH_KEY` | Private half of a read-only deploy key registered on the ROM repository |

The deploy key should grant read access only to the ROM repository; no personal
access token or organization-wide credential is required. The workflow checks
out source and private inputs into sibling directories, fetches public Git
dependencies and verifies hashes before building. Private input settings stay
out of the organization's template. Open Actions in your own clone, choose
**Private ROM build (manual opt-in)** and **Run workflow**.

## Input identity and outputs

The explicit ZIP is limited to 64 MiB and 64 members and contains exactly one
US retail and one Chinese v1.1 ROM, each 16 MiB. Member names and subdirectories
do not select roles. SHA-256 identifies them; wrong versions, missing inputs and
duplicate matches fail. ZIP paths are never extracted.

| Role | Required SHA-256 |
| --- | --- |
| US retail | `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19` |
| US Chinese v1.1 | `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03` |

`default` builds CN/pinyin/link/Info/italic and enabled custom plugins.
`exact-reference` disables optional built-in changes and requires the final ROM
to match the CN reference; disable custom plugins that alter it.

Only the IPS and hash report are published as seven-day Actions artifacts.
Both profiles first verify full CN resource reconstruction. ROMs, fonts, text,
private packs, dependency checkouts and build caches are never uploaded as
artifacts. An `always()` cleanup removes the job's private checkout and generated
resources. Disable the repository opt-in variable to skip future manual builds.

GitHub's [manual workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
explains dispatching from the default branch.
