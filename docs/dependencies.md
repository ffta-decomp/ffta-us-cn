# Public Git dependencies

`config/dependencies.lock.json` records public upstream URLs, complete Git
revisions and SHA-256 hashes for the required source files. No `vendor/` files
are tracked by the template or included in its source archive.

After cloning or extracting project source, run:

```sh
python3 tools/fetch_dependencies.py
python3 tools/verify_vendor.py
```

The fetcher retrieves the pinned Git commits into ignored `vendor/` checkouts.
It initializes the decomp project's pinned `vendor/agbcc` submodule and checks
that compiler revision against the host lock. The Rime dictionary and Apache
license are fetched from the pinned public Rime repository. Required file
hashes are checked before installation; existing checkouts are verified rather
than overwritten. Builds do not fetch or update dependencies implicitly.

Never patch dependency files locally. Generic changes belong in upstream PRs,
followed by an explicit reviewed lock update. Compiler outputs and caches stay
outside the source checkout. Upstream copyright and license notices remain in
the fetched checkouts; source archives provide their URLs, revisions and license
metadata instead of embedding the dependency implementations.
