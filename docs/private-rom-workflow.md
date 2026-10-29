# Optional private ROM workflow

`.github/workflows/private-rom-build.yml` has only `workflow_dispatch`; push,
pull requests and schedules never start it. It also requires the repository
variable `ENABLE_PRIVATE_ROM_BUILD` to equal `true`. Without that opt-in, the
build job is skipped even when manually dispatched.

## Configure your fork

1. Make a private ZIP containing your own US retail and US Chinese v1.1 ROMs.
   File names and subdirectories do not matter. Do not commit the ZIP or ROMs.
2. Store a private, direct HTTPS download URL in the Actions repository secret
   `PRIVATE_ROM_ARCHIVE_URL`. A signed object-storage URL works; a web login
   page or sharing-preview page does not. The download must return ZIP bytes.
   HTTPS redirects are supported. Alternatively upload the ZIP as a release asset
   in this same private repository and use its API asset URL:
   `https://api.github.com/repos/OWNER/REPO/releases/assets/ASSET_ID`.
   The workflow's read-only `GITHUB_TOKEN` authenticates that same-repository
   request and is not forwarded on CDN redirects. No separate personal token is
   required. No URL or credentials belong in dispatch inputs.
3. Set the Actions repository variable `ENABLE_PRIVATE_ROM_BUILD` to `true`.
4. Ensure the workflow exists on your fork's default branch. Open Actions,
   choose **Private ROM build (manual opt-in)** and **Run workflow**. Select
   `default` or `exact-reference`.

The ZIP is limited to 64 MiB and 64 members. Each ROM must be exactly 16 MiB.
The script reads the explicitly supplied archive, hashes its members and writes
only matched ROMs under fixed temporary names. It never extracts member paths
or searches other directories. Wrong versions, missing inputs and duplicate
matches fail before resource import.

| Role | Required SHA-256 |
| --- | --- |
| US retail | `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19` |
| US Chinese v1.1 | `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03` |

## Build and outputs

The job verifies dependencies, runs tests, imports the CN ROM's resource pack,
and checks a complete byte-matched reconstruction before building. It derives
the pinyin/Info input map from the committed owner-provided CN v1.1 table,
validating every glyph and width against the supplied ROM. No external font,
OCR runtime, spreadsheet library or Swift environment is needed.

`default` uses the normal CN/pinyin/link/Info/italic options and enabled local
plugins. `exact-reference` disables those optional built-in changes and verifies
the final ROM's SHA-256 against the CN reference; disable your own custom
plugins if they change that output.

Only `ffta-us-cn.ips` and `build-report.json` are uploaded, with seven-day
retention. The report contains hashes and reconstruction results. ROMs, fonts,
text, resource packs, build directories and compiler logs are not uploaded or
cached. An `always()` cleanup step removes the job's private temporary directory
and publication directory. Builds run in a fresh hosted Ubuntu job using Python,
Clang, Make and ARM binutils. See the workflow run for hosted execution results.

Unset the opt-in variable to disable the job again. This repository does not
trigger the workflow or configure your private secret on your behalf.

GitHub documents manual dispatch in
[Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
