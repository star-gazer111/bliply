from flask import Flask
from data.providers import load_providers
from strategy.optimizer import RPCOptimizer
from api.v1.optimizer_routes import optimizer_bp, init_routes

# Initialize Flask app
app = Flask(__name__)

# Load providers
providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

# Initializing the RPCOptimizer
optimizer = RPCOptimizer(providers, enable_exploration=False)

# Initializing and registering the routes
init_routes(providers, provider_dict, optimizer)
app.register_blueprint(optimizer_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6969, debug=True)
