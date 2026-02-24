# sync-to-local-or-remote

CLI tools for syncing files between local folders and remote targets (Nextcloud public shares).

## Features

### sync-to-local (download)

- One-shot sync: run once, download new files, exit
- Manifest-based change detection (etag tracking)
- Recursive folder sync preserving directory structure
- Per-file pipelines: regex-matched command chains (e.g., ffmpeg conversion)
- Post-sync commands: run final actions after all downloads complete
- Index-only mode: seed manifest without downloading
- CLI args + JSON config (CLI overrides config)

### sync-to-remote (upload)

- Upload local files to a remote Nextcloud public share
- Manifest-based change detection (SHA256 hashing)
- Recursive folder upload preserving directory structure
- `--file-filter` regex to limit which files are uploaded
- Index-only mode: seed manifest without uploading
- CLI args + JSON config (CLI overrides config)

## Setup

```
install.bat
```

## Usage

### sync-to-local

#### With CLI arguments

```
start.bat --source-url "https://share.example.com/s/TOKEN?dir=/_folder" --target-dir ./output
```

#### With config file

```
start.bat --config config.json
```

#### Index-only (seed manifest without downloading)

```
start.bat --config config.json --index-only
```

### sync-to-remote

#### With CLI arguments

```
start_upload.bat --source-dir ./local_files --target-url "https://share.example.com/s/TOKEN"
```

#### With config file

```
start_upload.bat --config config_upload.json
```

#### Upload only .apk files

```
start_upload.bat --config config_upload.json --file-filter "\.apk$"
```

#### Index-only (seed manifest without uploading)

```
start_upload.bat --config config_upload.json --index-only
```

## CLI Arguments

### sync-to-local

```
sync-to-local --source-url URL --target-dir PATH
              [--source-type nextcloud]
              [--source-subdir /path]
              [--password PW]
              [--config config.json]
              [--manifest-path PATH]
              [--retries N] [--timeout N]
              [--log-level DEBUG|INFO|WARNING]
              [--index-only]
```

The `?dir=` query parameter in `--source-url` is auto-extracted as `--source-subdir`.

### sync-to-remote

```
sync-to-remote --source-dir PATH --target-url URL
               [--target-type nextcloud]
               [--target-subdir /path]
               [--password PW]
               [--config config_upload.json]
               [--manifest-path PATH]
               [--retries N] [--timeout N]
               [--log-level DEBUG|INFO|WARNING]
               [--index-only]
               [--file-filter REGEX]
```

The `?dir=` query parameter in `--target-url` is auto-extracted as `--target-subdir`.

`--file-filter` accepts a Python regex pattern. Only files whose relative path matches the pattern are uploaded. Examples: `\.apk$` (APK files only), `^docs/` (files under docs/ folder).

## Config Files

See `config_example.json` for a download example and `config_upload_example.json` for an upload example.

### Pipelines

Per-file command chains matched by regex. Only the first matching pipeline runs. On failure, remaining commands for that file are skipped.

Placeholders: `{file}` (full path), `{file_stem}` (no extension), `{file_name}` (filename only), `{file_dir}` (parent directory).

### Routes

File-routing rules that move downloaded files to different directories based on filename patterns. Routes run after all downloads and pipelines complete, before post-sync commands. Skipped in `--index-only` mode and when no new files were downloaded.

Each route has a `pattern` (regex matched against the filename) and a `target_dir` (destination directory). The first matching route wins. Relative paths are resolved against the config file's parent directory; absolute paths are used as-is.

```json
"routes": [
  {"pattern": "\\.mp3$", "target_dir": "../../Assets/Audio"},
  {"pattern": "\\.mp4$", "target_dir": "D:/Unity3D/project/Assets/StreamingAssets"}
]
```

### Post-sync commands

Commands that run once after all downloads, pipelines, and routes complete. Only runs if at least one file was downloaded. Skipped in `--index-only` mode.

Placeholders: `{target_dir}` (the target directory path).

## Development

```
tools\tests.bat          # run tests
uv run ruff check src/ tests/  # lint
uv run mypy src/               # type check
update.bat               # update dependencies + lint + test
```
