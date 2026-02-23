#!/bin/bash

# Define the root directory (current directory)
PROJECT_ROOT="."

# Create core directory and files
mkdir -p core
touch core/config.py
touch core/logging_setup.py
touch core/exceptions.py
touch core/constants.py

# Create data directory and files
mkdir -p data
touch data/__init__.py
touch data/providers.py
touch data/metrics.py
mkdir -p data/schemas
touch data/schemas/rpc_request.py
touch data/schemas/rpc_response.py

# Create services directory and files
mkdir -p services
touch services/__init__.py
touch services/rpc_client.py
touch services/metric_collector.py
touch services/quota_manager.py
touch services/health_checker.py
touch services/db_service.py

# Create strategy directory and files
mkdir -p strategy
touch strategy/__init__.py
touch strategy/normalizer.py
touch strategy/critic_weights.py
touch strategy/scoring_engine.py
touch strategy/selector.py

# Create api directory and files
mkdir -p api
touch api/__init__.py
mkdir -p api/v1
touch api/v1/__init__.py
touch api/v1/optimizer_routes.py
mkdir -p api/middleware
touch api/middleware/request_logger.py

# Create tests directory and files
mkdir -p tests/unit
touch tests/unit/test_normalizer.py
touch tests/unit/test_critic_weights.py
touch tests/unit/test_selector.py
mkdir -p tests/integration
touch tests/integration/test_rpc_client.py
touch tests/integration/test_metric_collector.py
mkdir -p tests/mocks

# Create scripts directory and files
mkdir -p scripts
touch scripts/init_db.py
touch scripts/run_optimizer.py
touch scripts/generate_test_data.py

# Create root level files
touch main.py
touch requirements.txt
touch Dockerfile
touch README.md
touch .env.example

echo "Project directory structure created successfully in the current directory!"