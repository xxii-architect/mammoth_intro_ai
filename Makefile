# Makefile

PYTHON := python

.PHONY: smoke test

smoke:
    $(PYTHON) tools/quick_smoke_test.py

test:
    pytest -q
