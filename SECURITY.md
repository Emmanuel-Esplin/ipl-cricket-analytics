# Security

Report a vulnerability through GitHub's private vulnerability reporting
("Security" tab, "Report a vulnerability"), not a public issue.

## What protects this repo

- No secrets in code: AWS access uses short-lived credentials (`aws login` locally, IAM roles in
  AWS). gitleaks runs on every push, and GitHub push protection blocks known secret formats.
- Dependencies are locked (`requirements.lock`) and audited with pip-audit in CI. Dependabot
  proposes updates after a 7-day cooldown, so a freshly published malicious release is not picked
  up straight away.
- GitHub Actions are pinned to commit SHAs, run with read-only tokens, and are checked by zizmor.
- AWS: the bucket blocks public access and refuses non-TLS requests; each Lambda has its own role
  limited to the prefixes it needs; Athena has a per-query scan cap and a budget alert exists.
- The Lambda image is scanned by ECR on every push. Open findings are reviewed before deploying.

## Known findings

All are OS packages in the AWS Lambda base image (AL2023), none in the Python dependencies. On
2026-11-11 each was already the newest version AL2023 offered, so a rebuild can't fix them yet.
The functions take no inbound traffic and only make outbound HTTPS calls to Cricsheet and AWS.

| Date | Finding | Where | Status |
| --- | --- | --- | --- |
| 2026-11-11 | CVE-2026-103242, CVE-2026-84837, CVE-2026-95519 (High) | `rpm`, `rpm-libs` | Package manager, not used at runtime. Rebuild when fixed. |
| 2026-11-11 | CVE-2026-86805 (High) | `glibc` | No fixed package yet. Rebuild when AL2023 ships one. |
| 2026-11-11 | CVE-2026-18924, CVE-2026-19931 (Medium) | `curl-minimal`, `libcurl-minimal` | The pipeline uses httpx, not curl. Rebuild when fixed. |
| 2026-11-11 | CVE-2026-114406 (Medium): weak-key eMudhra roots | `ca-certificates` | HTTP clients use certifi's bundle, not the system store. |
| 2026-11-11 | CVE-2026-76781 (Medium) | `libxml2` | The pipeline parses no XML. |
