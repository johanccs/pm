# Scripts

Start and stop scripts for running the Docker container locally.

| Script | Platform | Action |
|--------|----------|--------|
| `start.ps1` | Windows | `docker compose up --build -d` |
| `stop.ps1` | Windows | `docker compose down` |
| `start.sh` | Mac/Linux | `docker compose up --build -d` |
| `stop.sh` | Mac/Linux | `docker compose down` |

Run from any directory — scripts resolve paths relative to the project root.
