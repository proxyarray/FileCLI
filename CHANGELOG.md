# Changelog

## 0.2.0 — 2026-11-03

- Redesigned the interface with the black-and-white MUSOS INDIA identity, extension-colored filenames, aligned columns, and responsive dual/single-pane layouts.
- Made Escape navigate back, close modal screens, or request cancellation of an active file operation.
- Moved directory enumeration and metadata collection to background workers and added chunked table population to keep large listings responsive.
- Prevented concurrent copy/move requests from cancelling or interfering with one another.
- Improved sorting so directories remain grouped before files in either direction, including when a file disappears during sorting.
- Made invalid settings produce a concise startup error.
- Added Python 3.11/3.12 CI, package metadata, and distribution build verification.

## 0.1.0

- Initial public implementation with Textual dual-pane browsing, safe basic file operations, search, previews, archives, storage information, themes, settings, and tests.
