# Security policy

The plugin processes microphone audio locally in a restricted WebAssembly
environment. It has no host imports or network access, but package parsing,
model loading, memory bounds, and the host/plugin boundary remain
security-sensitive.

## Supported versions

Security fixes target the current `main` branch and the package at the newest
documented immutable revision.

## Reporting a vulnerability

Use this repository's GitHub **Report a vulnerability** feature. If it is
unavailable, contact a repository owner privately. Do not open a public issue
for a suspected vulnerability.

Include the affected commit, impact, reproduction steps using synthetic or
consented audio, and mitigation if known. Do not submit private recordings or
credentials. The project does not currently promise a response SLA or bug bounty.

