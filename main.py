from fastapi import FastAPI
from providers.registry import load_providers
from strategy.optimizer import RPCOptimizer
import logging
from api.v1.optimizer_routes import router

app = FastAPI()
app.include_router(router, prefix="/api")

providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

optimizer = RPCOptimizer(providers, enable_exploration=False)
