.PHONY: install generate evaluate report test backend dashboard clean

install:
	pip install -r requirements.txt

generate:
	python scripts/generate_data.py --count 5000

evaluate:
	python scripts/run_batch.py --limit 5000 --llm-limit 50

report:
	python scripts/evaluate.py

test:
	python -m pytest tests/

backend:
	python app/main.py

dashboard:
	streamlit run dashboard/app.py

clean:
	@if exist recoverai.db del recoverai.db
	@if exist .pytest_cache rmdir /s /q .pytest_cache
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	@if exist data\generated rmdir /s /q data\generated
	@if exist data\evaluation rmdir /s /q data\evaluation
	@mkdir data\generated data\evaluation
	@echo # gitkeep > data\generated\.gitkeep
	@echo # gitkeep > data\evaluation\.gitkeep
