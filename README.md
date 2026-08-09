# SUP → SRT GitHub Web Converter

Personal bulk Blu-ray PGS/SUP → SRT OCR converter powered by GitHub Pages + GitHub Actions.

## Architecture

- `docs/` — static GitHub Pages UI.
- `.github/workflows/convert.yml` — Ubuntu worker.
- `.github/workflows/pages.yml` — deploys `docs/` to GitHub Pages.
- `tools/clean_srt.py` — SRT cleanup.
- The browser creates a temporary `jobs/<id>` branch through the GitHub Git Data API and uploads all selected `.sup` files there.
- GitHub Actions processes the files sequentially, cleans the SRTs, and uploads the resulting SRT directory as one workflow artifact. GitHub's artifact download is itself a ZIP containing all generated SRT files.
- The temporary branch is deleted after the job, even if the conversion fails.

## Security

This is intended as a personal tool. The Pages site asks for a fine-grained GitHub Personal Access Token in the browser.

Create the token with access to this repository only and:
- Contents: Read and write
- Actions: Read and write

The token is kept only in memory by the page. It is not put into the repository, URL, localStorage, or cookies.

Do NOT hard-code your token in JavaScript.

## OCR

The worker uses Subtitle Edit's headless `seconv` CLI and Tesseract. Subtitle Edit documents direct Blu-ray `.sup` → SubRip conversion with:

    seconv movie.sup subrip --ocr-engine:tesseract --ocr-language:eng

The workflow pins Subtitle Edit v5.0.0 for reproducibility.

## GitHub Pages

Enable Pages from `Settings → Pages` and choose `GitHub Actions` as the source.

## Use

1. Push this project to your GitHub repository.
2. Enable GitHub Pages with GitHub Actions.
3. Create a fine-grained PAT limited to this repository.
4. Give it Contents read/write and Actions read/write.
5. Open the Pages URL.
6. Enter `owner/repository` and paste the token.
7. Select all `.sup` files.
8. Choose cleaning options.
9. Start the job.
10. When it finishes, the page downloads the generated ZIP directly when possible. A fallback link to the Actions run is also shown.
