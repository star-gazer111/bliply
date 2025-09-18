#!/bin/bash
set -e

while read -r f; do
  mkdir -p "$(dirname "$f")"
  : > "$f"
done <<'EOF'
core/config.py
core/logging_setup.py
core/exceptions.py
core/constants.py
data/__init__.py
data/providers.py
data/metrics.py
data/schemas/rpc_request.py
data/schemas/rpc_response.py
services/__init__.py
services/rpc_client.py
services/metric_collector.py
services/quota_manager.py
services/health_checker.py
services/db_service.py
strategy/__init__.py
strategy/normalizer.py
strategy/critic_weights.py
strategy/scoring_engine.py
strategy/selector.py
api/__init__.py
api/v1/__init__.py
api/v1/optimizer_routes.py
api/middleware/request_logger.py
tests/unit/test_normalizer.py
tests/unit/test_critic_weights.py
tests/unit/test_selector.py
tests/integration/test_rpc_client.py
tests/integration/test_metric_collector.py
scripts/init_db.py
scripts/run_optimizer.py
scripts/generate_test_data.py
main.py
requirements.txt
Dockerfile
README.md
.env.example
EOF

mkdir -p tests/mocks
echo "Project directory structure created successfully in the current directory!"
