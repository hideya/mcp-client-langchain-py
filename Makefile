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

build:
	uv build
	@echo
	uvx twine check dist/*

publish:
	uvx twine upload --verbose \
		--repository-url https://upload.pypi.org/legacy/ dist/* \
		--password ${PYPI_API_KEY}

test:
	python -m pytest tests/ -v

clean:
	git clean -fdxn -e .env
	@read -p 'OK?'
	git clean -fdx -e .env
