# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 2.0.x   | Yes       |
| < 2.0   | No        |

## Reporting a vulnerability

Do not open a public issue or pull request for a security problem.

Report it privately with **Report a vulnerability** on the Security tab of
https://github.com/ks-rdz-07/junk-cleaner-2.0 (GitHub private vulnerability reporting).

Please include:

- The Junk Cleaner version (shown under the title in the sidebar) and your Windows or Linux version.
- Steps to reproduce, and the impact you expect.
- The file or code involved, if you know it.
- A proof of concept, kept to the minimum needed. Do not include personal data.

We aim to acknowledge every report within 7 days.

## Security model

- **Elevation.** On Windows, the installed app runs elevated (UAC). When started from source, it asks
  for elevation unless `--no-elevate` is given.
- **Scanning is read-only.** The junk scan lists files and never changes them.
- **Deletion needs confirmation.** Cleanup (Recycle Bin, quarantine or permanent delete), permanent
  quarantine delete, clearing history, and a virus scan each ask first. The default answer is No.
  Exception: once you confirm a Safety Scanner run, it removes the threats it finds.
- **Quarantine.** Confirmed items are moved to `%LOCALAPPDATA%\JunkCleaner\quarantine`. Each payload is
  renamed to `payload` with no extension, so a quarantined program cannot be started by double-clicking it.
  Quarantined items are deleted automatically 30 days after quarantine, at startup, without a further prompt.
- **Microsoft Safety Scanner.** Downloaded from Microsoft's download link (`go.microsoft.com`) when it is
  missing or older than 10 days. Before every run, its Authenticode signature must be `Valid` and signed by
  Microsoft Corporation. If the check fails, the file is deleted and nothing runs. It runs elevated.
- **Updates.** Junk Cleaner does not update itself. Outdated apps listed on the Security page are upgraded
  with winget, after confirmation.
- **Network access.** Junk Cleaner has no telemetry and no analytics. Its network activity is limited to:
  - the Safety Scanner download described above;
  - the Windows Update search (run through PowerShell and the Windows Update COM API) on the Security page;
  - winget, which contacts its package sources when checking or upgrading apps;
  - opening a CVE record in your browser, only when you choose to open one from the Security page.

  On Linux, the security features are disabled, so the app makes no network calls.
- **Local data.** History and quarantine are stored in `%LOCALAPPDATA%\JunkCleaner` on Windows
  (`~/.local/share/JunkCleaner` on Linux).
