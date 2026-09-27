# Atalhos do JEV Leads Lab (requer `make`; no Windows sem make use os comandos `uv run`).
SAMPLE ?= 300

.PHONY: help sync inspect smoke states enrich all metrics dash test fixture clean

help:
	@echo "Alvos: sync inspect smoke states enrich all metrics dash test fixture"

sync:
	uv sync

inspect:
	uv run python scripts/01_inspect.py

smoke:
	uv run python scripts/00_smoke_jev.py

fixture:
	uv run python scripts/00_smoke_jev.py --save-fixture

states:
	uv run python scripts/02_build_states.py

enrich:
	uv run python scripts/03_enrich.py --limit $(SAMPLE)

all:
	uv run python scripts/03_enrich.py --all

metrics:
	uv run python scripts/04_metrics.py

dash:
	uv run streamlit run src/jevlab/dashboard/app.py

test:
	uv run pytest

clean:
	rm -rf outputs/cache outputs/metrics outputs/enriched*.parquet
