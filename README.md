# SUP → SRT GitHub Web Converter

Personal bulk Blu-ray PGS/SUP → SRT OCR converter powered by GitHub Pages + GitHub Actions.

## Architecture

- `docs/` — static GitHub Pages UI.
- `.github/workflows/convert.yml` — Ubuntu OCR worker.
- `.github/workflows/pages.yml` — deploys `docs/` to GitHub Pages.
- `tools/clean_srt.py` — SRT cleanup.
- The browser creates a temporary `jobs/<id>` branch through the GitHub Git Data API and uploads all selected `.sup` files there.
- GitHub Actions processes files sequentially, cleans the generated SRT files, creates one ZIP, and uploads it as an artifact.
- The temporary branch is deleted after processing, including after failures.

## OCR

The worker builds Subtitle Edit's current headless `seconv` from source and publishes it for Linux x64. It then uses:

`seconv movie.sup subrip --ocr-engine:tesseract --ocr-language:eng`

Subtitle Edit documents Blu-ray `.sup` → SubRip conversion and Tesseract OCR in its command-line documentation.

## GitHub Pages

Enable Pages from `Settings → Pages` and choose `GitHub Actions` as the source.

## Token

Use a fine-grained GitHub token restricted to this repository with:

- Contents: Read and write
- Actions: Read and write

The token stays in browser memory and is not stored in the repository, URL, localStorage, or cookies.
