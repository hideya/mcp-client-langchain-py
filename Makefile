# NOTES: 
# - The command lines (recipe lines) must start with a TAB character.
# - Each command line runs in a separate shell without .ONESHELL:
.PHONY: install start start-v start-h build clean
.ONESHELL:

.venv:
	uv venv

install: .venv
	uv pip install .

start:
	uv run src/mcp_chat/cli_chat.py $(filter-out start,$(MAKECMDGOALS))

clean:
	rm -rf dist *.log logs

cleanall:
	git clean -fdxn -e .env
	@read -p 'OK?'
	git clean -fdx -e .env

build: clean
	uv build
	@echo
	uvx twine check dist/*

prep-publish: build
	# set PYPI_API_KEY from .env
	$(eval export $(shell grep '^PYPI_API_KEY=' .env ))

	# check if PYPI_API_KEY is set
	@if [ -z "$$PYPI_API_KEY" ]; then \
		echo "Error: PYPI_API_KEY environment variable is not set"; \
		exit 1; \
	fi

publish: prep-publish
	uvx twine upload \
		--verbose \
		--repository-url https://upload.pypi.org/legacy/ dist/* \
		--password ${PYPI_API_KEY}

test-publish: prep-publish
	tar tzf dist/*.tar.gz
	@echo
	unzip -l dist/*.whl
	@echo
	uvx twine check dist/*
