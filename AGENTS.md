# Repository Guidelines

## Project Structure & Module Organization
The GUI launcher lives in `src/gui` (Qt widgets and dialogs) while download orchestration and configuration helpers sit in `src/core`. Shared hooks for PyInstaller builds are under `src/hooks`. Runtime assets such as yt-dlp, ffmpeg, and helper batch scripts stay in `bin`; user-editable presets are written to `config`; UI images belong in `icons` and `screenshots`. Integration-style probes (e.g. `test_title_extraction.py`) sit at the repository root so they can be executed without packaging.

## Build, Test, and Development Commands
Always work inside the bundled virtual environment: `.\.venv\Scripts\activate`. Launch the GUI for live debugging with `python src/main.py`. Run quick behaviour checks via `python test_title_extraction.py` or `python test_log_feature.py`. Package a distributable build with `python build.py`; the bundled PyInstaller spec will emit artifacts into `dist/` and copy supporting binaries.

## Coding Style & Naming Conventions
Python modules use 4-space indentation, UTF-8 encoding, and descriptive snake_case identifiers. Qt widget subclasses follow the suffix `_window.py` to signal UI entry points. Prefer explicit imports, dataclasses where practical, and guard GUI side effects behind methods to keep `main.py` lean. Keep user-facing strings translatable and review each dialog for Chinese localisation consistency.

## Testing Guidelines
Lean on the existing manual harnesses for regression checks after any downloader or title parsing changes. Extend them with focused functions instead of ad-hoc prints. When adding automated tests, mirror the pattern in `test_title_extraction.py` and prefix filenames with `test_`. Aim to verify subtitle handling, playlist flows, and GUI logging before requesting review, and document any skipped scenarios.

## Commit & Pull Request Guidelines
Follow the repository history: concise, present-tense summaries in Chinese that explain the intent (e.g. "优化UI布局" or "更新yt-dlp内核到2025.6.9"). Group related fixes into a single commit; avoid mixing feature work with packaging housekeeping. Pull requests should describe motivation, summarize user-visible impact, attach relevant screenshots for UI updates, and reference linked issues or release checklists. Ensure builds succeed locally before marking ready for review.

## Release & Configuration Tips
Keep `version.txt` and the version string in `src/main.py` synchronized prior to packaging. Before publishing, refresh yt-dlp via `bin/更新内核.bat` and clear stale artifacts with `python clear_icon_cache.py`. Never commit personal cookies or per-user paths; sample configuration belongs in `config/` with placeholder values.