# Home Media Server

This repository runs a home media server with Docker Compose. It includes media playback, requests, automated downloads, subtitles, a dashboard, container management, logs, and uptime monitoring.

The stack expects:

- A Linux server running Docker.
- A network or local disk mounted at `/media/synology_media`.
- The repository checked out on the same server where Docker runs.
- The server user’s home directory available as `$HOME`.

The Compose file stores application configuration under `$HOME`. For example, if the Linux username is `media`, Jellyfin configuration is stored in `/home/media/jellyfin/config`.

## What is included

| Service | What it does | Address |
| --- | --- | --- |
| Jellyfin | Plays movies, series, and Live TV | `http://SERVER_IP:8096` |
| Homer | Dashboard with links to the services | `http://SERVER_IP/` |
| Jellyseerr | Lets users request movies and series | `http://SERVER_IP:5055` |
| Sonarr | Manages TV-series downloads | `http://SERVER_IP:8989` |
| Radarr | Manages movie downloads | `http://SERVER_IP:7878` |
| Bazarr | Downloads subtitles | `http://SERVER_IP:6767` |
| qBittorrent | Downloads torrents | `http://SERVER_IP:8080` |
| Prowlarr | Manages download indexers | `http://SERVER_IP:9696` |
| Portainer | Manages Docker containers | `http://SERVER_IP:9000` |
| Dozzle | Shows live container logs | `http://SERVER_IP:9999` |
| Uptime Kuma | Monitors service availability | `http://SERVER_IP:3001` |
| theme-downloader | Searches for missing theme songs | No web interface |

Replace `SERVER_IP` with the IP address of the Docker server. All services are connected to the same Docker network and can communicate using their service names.

## Install Docker

On a new Ubuntu or Debian server, install Docker by following the official instructions:

<https://docs.docker.com/engine/install/>

After installation, verify that both Docker and Compose are available:

```sh
docker --version
docker compose version
```

The commands in this README use Docker Compose v2, which is invoked as `docker compose` with a space.

## Prepare the server

### 1. Mount the media storage

The media storage must be available at exactly:

```text
/media/synology_media
```

The following directories are expected inside it:

```text
/media/synology_media/shows
/media/synology_media/movies
/media/synology_media/downloads
```

Check the mount and directories before starting Docker:

```sh
mountpoint /media/synology_media
test -d /media/synology_media/shows
test -d /media/synology_media/movies
test -d /media/synology_media/downloads
```

If the storage is a Synology share, configure the system mount separately so it is mounted before Docker starts.

### 2. Check the home directory

Run the Compose commands as the Linux user who owns the application data. Confirm that `$HOME` points to the expected directory:

```sh
printf '%s\n' "$HOME"
```

For a user named `media`, the output should be `/home/media`.

The Compose file creates or uses these directories under `$HOME`:

```text
$HOME/jellyfin/
$HOME/jellyseerr/
$HOME/sonarr/
$HOME/radarr/
$HOME/bazarr/
$HOME/qbittorrent/
$HOME/prowlarr/
$HOME/portainer/
$HOME/uptime-kuma/
$HOME/theme-downloader/
$HOME/homer/
$HOME/sportyfin/output/
```

Do not delete an existing directory if it contains application configuration or a database.

### 3. Check the ports

Make sure these host ports are available:

```text
80, 3001, 5055, 6767, 7878, 8080, 8096, 8989, 9000, 9696, 9999, 6881/tcp, 6881/udp
```

If another application already uses one of these ports, change the host-side port in `docker-compose.yml`. For example, changing `8096:8096` to `8097:8096` makes Jellyfin available on port `8097` while leaving its internal port unchanged.

## Download and start the stack

Clone the repository on the Docker server and enter its directory:

```sh
git clone <repository-url> dockerCompose
cd dockerCompose
```

Validate the Compose file:

```sh
docker compose config
```

Download the container images and start all services in the background:

```sh
docker compose pull
docker compose up -d
```

Check the result:

```sh
docker compose ps
```

Some services take a minute or two to become ready on their first start. View startup logs with:

```sh
docker compose logs --tail=100
docker compose logs -f jellyfin
```

Open Homer in a browser at `http://SERVER_IP/`. The other service addresses are listed above.

## First-time application setup

Each application has its own setup screen and credentials. Complete the setup in roughly this order:

1. Open qBittorrent and complete its initial setup.
2. Open Prowlarr and add your indexers.
3. Open Sonarr and configure your TV library, download client, and Prowlarr connection.
4. Open Radarr and configure your movie library, download client, and Prowlarr connection.
5. Open Bazarr and connect it to Sonarr and Radarr.
6. Open Jellyseerr and connect it to Jellyfin, Sonarr, and Radarr.
7. Open Jellyfin and add the libraries described below.
8. Configure Uptime Kuma monitors for the services you want to watch.

### Media paths inside containers

When configuring applications through their web interfaces, use the paths visible inside the relevant container, not the host paths.

| Media | Jellyfin path | Sonarr/Radarr/Bazarr/theme-downloader path | qBittorrent path |
| --- | --- | --- | --- |
| Shows | `/media/shows` | `/shows` | Not used |
| Movies | `/media/movies` | `/movies` | Not used |
| Downloads | Not used | `/downloads` | `/downloads` |

For example:

- Add `/media/shows` and `/media/movies` as Jellyfin library folders.
- Add `/shows` as the Sonarr root folder.
- Add `/movies` as the Radarr root folder.
- Configure qBittorrent's download location as `/downloads`.
- Configure Sonarr and Radarr to read completed downloads from `/downloads`.

Using `/media/synology_media/...` inside a container will not work because that is the host path, not the path mounted inside the container.

## Start automatically when the server boots

The containers use `restart: unless-stopped`, so Docker will restart them after a server reboot as long as Docker itself starts automatically.

Enable Docker at boot on a system using systemd:

```sh
sudo systemctl enable --now docker
```

Start the Compose stack once manually and leave it running:

```sh
cd /path/to/dockerCompose
docker compose up -d
```

After that, Docker will restart the containers after reboot. Make sure the media storage is mounted before Docker starts; otherwise services may start while the libraries are unavailable.

## Updating the stack

Pull newer images and recreate containers when necessary:

```sh
cd /path/to/dockerCompose
docker compose pull
docker compose up -d
```

Check the result:

```sh
docker compose ps
docker compose logs --tail=100
```

The Compose file uses `latest` image tags. This means an update can include upstream changes, so check the service logs after updating.

## Everyday Docker commands

```sh
# Show container status
docker compose ps

# Follow logs for one service
docker compose logs -f jellyfin

# Show the last 200 log lines
docker compose logs --tail=200 sonarr

# Restart one service
docker compose restart jellyfin

# Stop the stack
docker compose stop

# Start the stack again
docker compose start

# Stop and remove containers
docker compose down
```

`docker compose down` removes the containers but does not remove the application data stored in the host directories. Do not use volume-removal commands unless you understand exactly what data they will delete.

## Maintenance scripts

### Theme downloader

The `theme-downloader` service checks the shows and movies directories once per day. If a media folder does not contain `theme.mp3`, it searches YouTube and saves a theme song there.

The interval can be changed in `docker-compose.yml` with `DOWNLOAD_INTERVAL_SECONDS`.

### Trickplay progress

Jellyfin can generate trickplay images for supported video files. To report which MKV files have a matching `.trickplay` directory, run this on the Docker host:

```sh
./tools/check-trickplay-progress.sh /media/synology_media/shows
```

To find orphaned `.trickplay` directories without deleting anything:

```sh
./tools/cleanup-orphaned-trickplay.sh
```

Review the output first. To delete the reported orphaned entries:

```sh
./tools/cleanup-orphaned-trickplay.sh --delete
```

## Optional hardware transcoding

Jellyfin is given access to `/dev/dri` for hardware transcoding. This requires compatible graphics hardware and host drivers.

If the server does not have `/dev/dri`, remove or comment out this section in `docker-compose.yml`:

```yaml
devices:
  - /dev/dri:/dev/dri
```

Hardware transcoding must also be enabled in Jellyfin's Dashboard after the container is running.

## Environment file

This Compose project does not require a `.env` file. There is an `.env.example` file in the repository, but it is only an example for optional NordVPN-related settings and is not currently used by any service in `docker-compose.yml`.


## Troubleshooting

### A service is unhealthy

```sh
docker compose ps
docker inspect --format '{{json .State.Health}}' <container-name>
docker compose logs --tail=200 <service>
```

Jellyseerr, Sonarr, Radarr, Bazarr, qBittorrent, and Prowlarr have HTTP health checks. A service may need extra time during its first startup.

### Downloads are not imported

Check that:

- qBittorrent uses `/downloads` for downloads.
- Sonarr and Radarr also see completed files under `/downloads`.
- Sonarr uses `/shows` as its root folder.
- Radarr uses `/movies` as its root folder.
- The relevant containers can read and write the media directories.

### Jellyfin cannot see the media

Check that the storage is mounted on the host:

```sh
mountpoint /media/synology_media
docker compose exec jellyfin ls -la /media
```

Also check that the media directories can be read by the container.

### A port is already in use

Find the process using a port:

```sh
sudo ss -ltnup
```

Then either stop the conflicting service or change the host-side port mapping in `docker-compose.yml`.

### View a service's logs

```sh
docker compose logs --tail=200 <service>
docker compose logs -f <service>
```

Replace `<service>` with a Compose service name such as `jellyfin`, `sonarr`, or `qbittorrent`.
