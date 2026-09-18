# Server Audit Checklist (Phase 0)

**This is a checklist template, not a completed audit — it contains no
results.** It was produced inside an isolated build session with no
SSH/Docker access to your production server; running commands here would
only describe that sandbox, not your real infrastructure. Run every command
below **on the real target server**, read-only, and record the output in
the matching section (by hand, or by running `scripts/server-audit.sh`,
which gathers everything below into one timestamped file for you to
review/attach). Do not deploy anything until this document says **READY**.

## How to fill this in

SSH into the target server yourself (or hand this file + a terminal to
whoever runs Phase 0), then either run `../scripts/server-audit.sh` (from
`docs/`) to gather everything at once, or run these individually:

```bash
hostname
uname -a
cat /etc/os-release

docker --version
docker compose version

docker ps
docker ps -a

docker network ls
docker volume ls

df -h
free -h

ss -lntup
```

Do not print secrets (env vars, `.env` contents, tokens) into this file.

## OS

```
<paste `uname -a` and /etc/os-release output>
```

## Docker

- Docker version: `<paste>`
- Docker Compose version: `<paste>`

## Resources

- CPU: `<cores / model>`
- RAM: `<paste `free -h`>`
- Disk free: `<paste `df -h`, flag any filesystem above 80% used>`

## Current containers

```
<paste `docker ps` and `docker ps -a`>
```

## Current Docker networks

```
<paste `docker network ls`>
```

## Current Docker volumes

```
<paste `docker volume ls`>
```

## Ports in use (`ss -lntup`)

Check specifically for conflicts with the ports this stack cares about:

| Port | In use? | By what? | Conflict with this project? |
|------|---------|----------|------------------------------|
| 3000 | | | |
| 3080 | | | |
| 5432 | | | |
| 8000 | | | |
| 8080 | | | |
| 8090 | | | |
| 8888 | | | |
| 9000 | | | |
| 8077 (gateway default, see `.env.example`) | | | |

If 5432 is already bound to an existing Postgres (e.g. Odoo's), that is
expected and fine — this stack's Postgres container does **not** publish a
host port at all (see `docker/docker-compose.yml`), so there is no
collision at the Docker level either way. Still record it here for
awareness.

## Existing related services found

- [ ] Hermes — `<container name / how it's running>`
- [ ] OpenClaw — `<container name / how it's running>`
- [ ] Odoo — `<container name>`
- [ ] n8n — `<container name>`
- [ ] DeepSeek Harness — `<container name>`
- [ ] Any existing PostgreSQL — `<container name, is it Odoo's?>`
- [ ] Redis — `<container name>`
- [ ] Cloudflare Tunnel — `<config location>`
- [ ] Nginx / Traefik / Caddy — `<config location, existing routes>`

## Risks / conflicts identified

`<list anything that must be resolved before deploying — port collisions,
disk pressure, an existing `ngocviet-memory-net` network name already in
use, an existing volume name clash, etc. If anything here is unresolved,
the conclusion below MUST be BLOCKED, not READY.>`

## Conclusion

`<READY | BLOCKED>` — `<one-line reason>`

Only proceed to Phase 1 (`docs/deployment.md`) once this says READY.
