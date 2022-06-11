.PHONY: all mypy pylint fix
all: fix mypy pylint

fix:
	python -m black src
	python -m isort src

mypy:
	python -m mypy src

pylint:
	python -m pylint src
