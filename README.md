# SUP → SRT GitHub Web Converter

Personal bulk Blu-ray PGS/SUP → SRT OCR converter powered by GitHub Pages + GitHub Actions.

## Architecture

- `docs/` — static GitHub Pages UI.
- `.github/workflows/convert.yml` — Ubuntu OCR worker.
- `.github/workflows/pages.yml` — deploys `docs/` to GitHub Pages.
- `tools/clean_srt.py` — SRT cleanup.
- The browser creates a temporary `jobs/<id>` branch through the GitHub Git Data API and uploads all selected `.sup` files there.
- GitHub Actions processes files sequentially, cleans the generated SRT files, creates one ZIP (including a `conversion-report.txt`), and uploads it as an artifact.
- The temporary branch is deleted after processing, including after failures.

## OCR

The worker uses Subtitle Edit's headless `seconv` converter:

```
seconv movie.sup subrip --ocr-engine:tesseract --ocr-language:eng --output-folder:output --overwrite
```

**seconv acquisition strategy (this is the part that was previously broken):**

1. **Preferred path:** download the official prebuilt `SeConv-Linux-x64.tar.gz` asset that Subtitle Edit's own release workflow attaches to its GitHub releases. This binary is self-contained — it needs no .NET runtime or SDK on the runner at all — so this path never touches NuGet/.NET restore and cannot hit `project.assets.json not found`. The workflow verifies the download's SHA-256 checksum against the value GitHub reports for the asset, and sanity-checks the binary by running `--help` before trusting it.
2. **Fallback path:** if the prebuilt asset can't be found (e.g. Subtitle Edit stops shipping it) or fails its checksum/sanity check, the workflow builds `seconv` from the official source instead, with the correct sequence: `dotnet restore` **before** `dotnet build`/`publish` (the previous failure was caused by building before restoring).

Both paths were tested against a real `.sup` file during development of this fix (see **Testing performed** below).

### A real, non-obvious bug we found and fixed: `TERM`

`seconv` renders its console output with a UI library that silently prints an **empty box with no text** (while still exiting with code 0) when the `TERM` environment variable is unset or not one it recognizes. GitHub Actions runners don't reliably set a `TERM` that satisfies it. This doesn't break the actual OCR conversion (that still works and still returns the correct exit code), but it *does* break anything that tries to read `seconv`'s text output, such as a `--help` sanity check. The workflow now sets `TERM: xterm-256color` at the job level so `seconv`'s output — and any check that depends on it — is reliable.

## Testing performed

Before shipping this fix, the pipeline was exercised directly (not just reasoned about):

- Downloaded the official `SeConv-Linux-x64.tar.gz` from Subtitle Edit's latest GitHub release and confirmed it runs on a plain Linux x86_64 box with no .NET installed.
- Converted the real `S01E01.eng.sup` file provided with this project end-to-end: `seconv` → Tesseract OCR → 430-entry `.srt`.
- Ran `tools/clean_srt.py` on that real OCR output and confirmed it correctly strips recognized sound effects, keeps unrecognized bracketed OCR noise untouched (conservative by design), and drops duplicate consecutive lines (430 → 418 entries).
- Simulated a full 3-file sequential job (2 valid `.sup` files + 1 intentionally invalid file): confirmed the batch continues past the failed file, correctly reports `SUCCESS`/`FAILED` per file with exit codes, and still produces a ZIP containing the successful `.srt` files plus a `conversion-report.txt` listing both the successes and the failure.
- Confirmed the `TERM` issue described above, reproduced it, and confirmed `TERM=xterm-256color` fixes it.

What was **not** tested (requires actually running inside GitHub Actions / GitHub Pages, which this environment cannot do): the browser-side blob/tree/commit/ref calls, workflow dispatch + polling, artifact download through the GitHub API from a browser, and branch cleanup. Those code paths were reviewed carefully but you should run one real end-to-end job after deploying to confirm your token/permissions are set up correctly.

## GitHub Pages

Enable Pages from `Settings → Pages` and choose `GitHub Actions` as the source.

## Token

Use a fine-grained GitHub token restricted to this repository with:

- Contents: Read and write
- Actions: Read and write

The token stays in browser memory and is not stored in the repository, URL, localStorage, or cookies.
