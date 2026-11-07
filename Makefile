PY ?= python3
VENV = backend/.venv
BIN = $(VENV)/bin

.PHONY: setup dev-api dev-web build run test

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e "./backend[dev]"
	cd frontend && npm install

dev-api:
	cd backend && ../$(BIN)/uvicorn lectern.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

run:
	cd backend && ../$(BIN)/uvicorn lectern.main:app --port 8000

test:
	cd backend && ../$(BIN)/python -m pytest -q
	cd frontend && npx tsc --noEmit && npx vitest run
