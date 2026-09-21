# IPG Digital Asset Engine

Centralized cloud execution environment for Ideal Performance Group's digital-asset research, creative generation, Meta Ads tooling, and automation workflows.

This repository is the deployable wrapper. The upstream Arcads skill pack is installed into the container at build time and is not treated as the application itself.

## Safety defaults
- Secrets live in Railway environment variables, never Git.
- Meta ad publishing remains PAUSED by default for review.
- Cloud execution is independent of any personal computer.
