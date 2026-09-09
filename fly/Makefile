PYTHON = python3
MAIN = fly.py
MAP ?= maps/easy/01_linear_path.txt

.DEFAULT_GOAL := run
.PHONY: install run visual debug clean lint lint-strict

install:
	@echo "Installing dependencies..."
	$(PYTHON) -m pip install flake8 mypy pygame


run:
	@echo "Running project..."
	$(PYTHON) $(MAIN) $(MAP)


visual:
	@echo "Running project with visualisation..."
	$(PYTHON) $(MAIN) $(MAP) --visual


debug:
	@echo "Starting debugger..."
	$(PYTHON) -m pdb $(MAIN) $(MAP)


clean:
	@echo "Cleaning cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete


lint:
	@echo "Running flake8..."
	$(PYTHON) -m flake8 .
	@echo "Running mypy..."
	$(PYTHON) -m mypy . --warn-return-any \
	--warn-unused-ignores \
	--ignore-missing-imports \
	--disallow-untyped-defs \
	--check-untyped-defs


lint-strict:
	@echo "Running flake8..."
	$(PYTHON) -m flake8 .
	@echo "Running mypy (strict)..."
	$(PYTHON) -m mypy . --strict
