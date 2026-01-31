from fastapi import FastAPI
from contextlib import asynccontextmanager
from providers.registry import load_providers
from strategy.optimizer import RPCOptimizer
from config.config import CACHE_CONFIG
import logging
from api.v1.optimizer_routes import router, init_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    global optimizer
    yield
    if optimizer:
        await optimizer.rpc_client.close()

app = FastAPI(lifespan=lifespan)
app.include_router(router, prefix="/api")

providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

optimizer = RPCOptimizer(
    providers, 
    enable_exploration=True, 
    exploration_rate=0.3,
    cache_ttl_seconds=CACHE_CONFIG["score_cache_ttl_seconds"]
)

init_routes(providers, provider_dict, optimizer)
