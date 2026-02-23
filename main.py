# Reload trigger
from fastapi import FastAPI
from contextlib import asynccontextmanager
from providers.registry import load_providers
from core.router import RPCOptimizer
import logging
import os
from dotenv import load_dotenv

# Force load .env at the very beginning
load_dotenv()

from api.v1.optimizer_routes import router, init_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    global optimizer
    yield
    if optimizer:
        await optimizer.rpc_client.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and container orchestration"""
    return {
        "status": "healthy",
        "service": "bliply-rpc-optimizer",
        "providers_loaded": len(providers) if 'providers' in globals() else 0
    }

app.include_router(router, prefix="/api")

providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

optimizer = RPCOptimizer(providers, enable_exploration=True, exploration_rate=0.1)

init_routes(providers, provider_dict, optimizer)
