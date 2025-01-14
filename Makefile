# NOTES: 
# - The command lines (recipe lines) must start with a TAB character.
# - Each command line runs in a separate shell.
.PHONY: install start start-v start-h build publish test clean

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

build:
	uv build
	@echo
	uvx twine check dist/*

publish:
	uvx twine upload --verbose \
	--repository-url https://upload.pypi.org/legacy/ dist/* \
	--password ${PYPI_API_KEY}

test:
	uvx pytest tests/ -v

clean:
	git clean -fdx -e .env
