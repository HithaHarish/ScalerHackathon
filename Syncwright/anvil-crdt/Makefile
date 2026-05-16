.PHONY: build test demo chaos edge engine-analysis writeup

build:
	cd engine && npm ci && npm run build

test: build
	cd engine && npm test
	python3 bench/self_check.py --adapter adapters.myteam:Engine --fk-policy tombstone --quick

demo: build
	python3 bench/self_check.py --adapter adapters.myteam:Engine --fk-policy tombstone --quick

chaos:
	python3 bench/run.py --adapter adapters.myteam:Engine --fk-policy tombstone --randomized-seeds 9999 31415 27182 16180 11235

edge:
	python3 bench/edge_cases.py --adapter adapters.myteam:Engine

engine-analysis:
	python3 bench/engine_test_analysis.py

writeup:
	python3 scripts/make_writeup_pdf.py
