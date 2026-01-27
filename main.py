from flask import Flask
from providers.registry import load_providers
from strategy.optimizer import RPCOptimizer
from api.v1.optimizer_routes import optimizer_bp, init_routes

app = Flask(__name__)

providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

optimizer = RPCOptimizer(providers, enable_exploration=False)

init_routes(providers, provider_dict, optimizer)
app.register_blueprint(optimizer_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6969, debug=True)
