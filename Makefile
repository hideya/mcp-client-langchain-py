# NOTES: 
# - The command lines (recipe lines) must start with a TAB character.
# - Each command line runs in a separate shell without .ONESHELL:
.PHONY: install start start-v start-h build test clean
.ONESHELL:

.venv:
	uv venv

install: .venv
	uv pip install .

start:
	uv run src/cli_chat.py

start-v:
	uv run src/cli_chat.py -v

start-h:
	uv run src/cli_chat.py -h

build: clean install
	uv build
	@echo
	uvx twine check dist/*

test: install
	uv pip install -e ".[dev]"
	.venv/bin/pytest tests/ -v

clean:
	git clean -fdxn -e .env
	@read -p 'OK?'
	git clean -fdx -e .env
