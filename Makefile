# Multiplayer Sudoku MLOps demo — common workflows.
# Run `make help` to list targets.

PYTHON ?= python
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python
MODEL  := sudoku_model.pkl

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(VENV): ## Create the local virtual environment
	$(PYTHON) -m venv $(VENV)

.PHONY: install
install: $(VENV) ## Install Python dependencies into the venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

.PHONY: dataset
dataset: install ## Generate the synthetic training dataset
	$(PY) -m ml.dataset

.PHONY: train
train: dataset ## Train the model and place it where both images expect it
	$(PY) -m ml.train
	cp $(MODEL) ml_service/$(MODEL)
	@echo "Model written to ./$(MODEL) and ml_service/$(MODEL)"

$(MODEL): ## Train only if the model artifact is missing
	$(MAKE) train

.PHONY: test
test: install ## Run the test suite
	$(PY) -m pytest -q

.PHONY: check
check: install ## Byte-compile sources and validate the compose file
	$(PY) -m compileall -q engine server ml ml_service blockchain
	docker compose config --quiet

.PHONY: build
build: $(MODEL) ## Build all service images (trains model first if needed)
	docker compose build

.PHONY: up
up: $(MODEL) ## Build and start the full stack in the foreground
	docker compose up --build

.PHONY: up-detached
up-detached: $(MODEL) ## Build and start the full stack in the background
	docker compose up --build -d

.PHONY: logs
logs: ## Follow logs for the application services
	docker compose logs -f game-server ml_service blockchain

.PHONY: ps
ps: ## Show running services
	docker compose ps

.PHONY: down
down: ## Stop services and remove containers
	docker compose down

.PHONY: clean
clean: ## Stop services, drop volumes, and remove generated artifacts
	-docker compose down -v
	rm -f $(MODEL) ml_service/$(MODEL) sudoku_dataset.csv
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: all
all: check train up ## Validate, train, and launch the stack
