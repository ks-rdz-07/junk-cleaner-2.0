# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning.

## [2.0.1]

### Added
- Checkboxes to choose which outdated apps to update.

### Changed
- Winget updates run in parallel, with per-app progress.

### Fixed
- A timeout in one app update no longer aborts the other updates.

## [2.0.0]

### Added
- PySide6 user interface.
- Overview dashboard with antivirus and firewall status.
- Quarantine page with history; quarantined items are deleted after 30 days.
- History log with filter and CSV export.
- Defender protection history on the Security page.

## [1.x]

Earlier releases used a tkinter user interface. Features:
- Junk file scan and cleanup.
- Microsoft Safety Scanner virus scan.
- Missing Windows updates, with their CVEs.
- Outdated apps via winget.
