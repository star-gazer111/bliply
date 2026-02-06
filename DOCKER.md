# Docker Deployment Guide

## Quick Start

### 1. Setup Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your actual RPC provider URLs:
```bash
CHAINSTACK_URL=https://ethereum-mainnet.core.chainstack.com/YOUR_API_KEY
ALCHEMY_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
QUICKNODE_URL=https://your-endpoint.quiknode.pro/YOUR_API_KEY/
PAID_PROVIDERS=chainstack
```

### 2. Build and Run with Docker Compose

```bash
# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f bliply

# Check status
docker-compose ps

# Stop the service
docker-compose down
```

### 3. Verify the Service

```bash
# Health check
curl http://localhost:8000/health

# Make a test RPC request
curl -X POST http://localhost:8000/api/rpc/best \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_blockNumber",
    "params": [],
    "id": 1
  }'
```

## Docker Commands

### Using Docker Compose (Recommended)

```bash
# Build the image
docker-compose build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

### Using Docker Directly

```bash
# Build the image
docker build -t bliply:latest .

# Run the container
docker run -d \
  --name bliply \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  bliply:latest

# View logs
docker logs -f bliply

# Stop container
docker stop bliply

# Remove container
docker rm bliply
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CHAINSTACK_URL` | Chainstack RPC endpoint | `https://...` |
| `ALCHEMY_URL` | Alchemy RPC endpoint | `https://...` |
| `QUICKNODE_URL` | QuickNode RPC endpoint | `https://...` |
| `PAID_PROVIDERS` | Comma-separated list of paid tier providers | `chainstack` or `alchemy,quicknode` |

### Volume Mounts

- **`./data:/app/data`** - Persists usage counter data across container restarts

### Port Mapping

- **`8000:8000`** - Maps host port 8000 to container port 8000


