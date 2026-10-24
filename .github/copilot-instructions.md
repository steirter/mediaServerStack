# Copilot instructions for this repository

## Purpose and architecture

This repository is a Docker Compose deployment for a self-hosted home media stack, not an application codebase with a package manager or unit-test runner. The authoritative configuration is `docker-compose.yml`, and the README describes the expected host layout and service flow.

At a high level:

- All services run on the same Docker network (`media`) and are expected to be reachable through their container service names or host ports.
- Media storage is mounted from the host at `/media/synology_media`, with the expected directories `/media/synology_media/shows`, `/media/synology_media/movies`, and `/media/synology_media/downloads`.
- Service configuration and state live under `$HOME` (for example `$HOME/jellyfin`, `$HOME/sonarr`, `$HOME/radarr`, `$HOME/qbittorrent`, `$HOME/homer`, `$HOME/prowlarr`, `$HOME/uptime-kuma`, and `$HOME/theme-downloader`).
- The stack includes Jellyfin, Homer, Jellyseerr, Sonarr, Radarr, Bazarr, qBittorrent, Prowlarr, Portainer, Dozzle, and Uptime Kuma.
- `theme-downloader` is a helper script in `./theme-downloader` that writes to a mounted data directory and reads media from the show/movie folders.

When changing service wiring, ports, or mount paths, read both `README.md` and `docker-compose.yml` together. This repo is operational/configuration-heavy, so one file alone rarely tells the full story.

## Build, test, and validation commands

This repository does not define a language-level build, lint, or unit-test workflow (`npm`, `pytest`, etc. are not part of the project). Validation is Docker-based.

Use these commands for the repo's actual checks:

```sh
# Validate the Compose file and environment interpolation
cd /path/to/dockerCompose
docker compose config

# Pull and start or refresh the stack
cd /path/to/dockerCompose
docker compose pull
docker compose up -d

# Check the stack state
cd /path/to/dockerCompose
docker compose ps

# Inspect logs for a specific service
cd /path/to/dockerCompose
docker compose logs --tail=100
docker compose logs -f jellyfin

# Restart a single service after a config change
cd /path/to/dockerCompose
docker compose restart jellyfin
```

There is no single “test” command for app logic because there are no application source tests in this repo. For config changes, prefer `docker compose config` first, followed by the smallest relevant service-level validation (`docker compose logs` or `docker compose restart <service>`).

## Key conventions specific to this repository

- Keep the host path assumptions consistent with the README. Do not switch to arbitrary local directories; the stack expects `/media/synology_media` and `$HOME`-scoped config directories.
- Treat `docker-compose.yml` as the source of truth for service names, ports, bind mounts, and networks. The README is operational guidance, not an alternative configuration source.
- `HOME` is required for all persistent config locations. If a change adds a bind mount or references `$HOME`, ensure the host user owns the directory and the path is valid before starting Docker.
- Container paths are not the same as host paths. For example, Jellyfin uses `/media/shows` and `/media/movies`, Sonarr/Radarr/Bazarr use `/shows`, `/movies`, and `/downloads`, and qBittorrent uses `/downloads`.
- The stack is built around long-running Docker images using `:latest`; updates are handled with `docker compose pull` and `docker compose up -d`, then verified through logs.
- `README.md` explicitly calls out required port availability and host setup. If you change a port in `docker-compose.yml`, also confirm whether the README's port list and setup instructions still match.
- `.env` is the local runtime environment file for secrets such as NordVPN credentials and should not be committed; use `.env.example` as a template if you need to add credentials or runtime settings.
- The repo includes helper scripts and generated data directories (for example `theme-downloader` and `wireguard`), which are part of the operational setup rather than an application library.

## Working style for this repo

- Prefer service-scoped validation over broad stack churn.
- Keep changes small and aligned with the Docker/deployment focus of the repository.
- If a change affects app setup or media paths, cross-check the README and Compose file before finalizing.
- Do not assume package-based tooling exists; this repository is configured around Docker Compose and host-level system setup.
