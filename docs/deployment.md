# Deployment

## Docker Compose (Recommended)

### Prerequisites

- Docker and Docker Compose installed
- Dataset files available on the host machine

### Configuration

1. Mount your datasets at the expected paths in `docker-compose.yml`
2. Set the `DATASETS_YAML` environment variable

### Start

```bash
docker compose down && docker compose up --build
```

This starts two services:
- **Backend** on port `8000` — FastAPI server
- **Frontend** on port `3000` — Next.js UI

### Docker Compose Reference

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.python
    ports: ["8000:8000"]
    volumes:
      - /path/to/hdc:/data/hdc
      - /path/to/hand_drawn:/data/hand_drawn
      - /path/to/database:/data/database
    environment:
      - DATASETS_YAML=/app/wire_detection/config/datasets.docker.yaml

  frontend:
    build: ./ui
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
```

## Manual Deployment

### Backend

```bash
uv venv && uv sync
uv run wire-tune --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd ui
pnpm install
pnpm build
pnpm start  # or: pnpm dev
```

### Production Considerations

- Set `DATASETS_YAML` to the Docker config path in production
- Use a reverse proxy (nginx/Caddy) for TLS and domain routing
- Frontend should set `NEXT_PUBLIC_API_URL` to the public backend URL
- Dataset paths must be accessible from the backend container
