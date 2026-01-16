# Repository Guidelines

## Project Structure & Module Organization
Source widgets and dialogs reside in `src/gui`, while download orchestration and helpers live in `src/core`. PyInstaller hook customizations stay in `src/hooks`. Runtime binaries such as yt-dlp, ffmpeg, or helper batch scripts are under `bin`, and UI imagery is kept in `icons` and `screenshots`. User-preserved presets and cache-clearing tools belong in `config`. Integration-style probes (for example `test_title_extraction.py`) sit at the repository root for quick execution without packaging.

## Build, Test, and Development Commands
Always activate the bundled virtual environment via `.\.venv\Scripts\activate` before running any Python commands. Launch the GUI with `python src/main.py` to validate widgets in real time. Sanity-check downloader behaviour with `python test_title_extraction.py` or `python test_log_feature.py`. Package a distributable using `python build.py`; artifacts will appear in `dist/` together with copied binaries. Refresh cached UI resources using `python clear_icon_cache.py` after icon updates.

## Coding Style & Naming Conventions
Python modules use UTF-8 encoding, four-space indentation, and descriptive `snake_case` names. Qt widget subclasses follow the `_window.py` suffix to signal UI entry points. Keep imports explicit, prefer dataclasses for structured data, and guard GUI side effects within methods so `main.py` stays lean. Maintain Chinese-localisable strings, and place reusable assets in the directories noted above.

## Testing Guidelines
Automated probes mimic the pattern in `test_title_extraction.py`; name new tests with the `test_*.py` convention and keep them runnable from the repo root. Extend these harnesses with focused helper functions instead of ad-hoc prints, and verify subtitle handling, playlist flows, and GUI logging before requesting review. Document any intentionally skipped scenario within the test file.

## Commit & Pull Request Guidelines
Keep commits concise, present-tense, and in Chinese (e.g., “更新下载流程”). Group related fixes into a single commit and avoid mixing feature work with packaging chores. Pull requests should explain motivation, summarize user-visible impact, attach relevant screenshots for UI modifications, and link issues or release checklist items. Ensure local builds pass before requesting review.

## Release & Configuration Tips
Synchronize `version.txt` with the version constant inside `src/main.py`. Before packaging, refresh yt-dlp via `bin/更新内核.bat` and clear stale UI caches using `python clear_icon_cache.py`. Never commit personal cookies or per-user paths; share sample configuration through files inside `config/` with placeholder values.
