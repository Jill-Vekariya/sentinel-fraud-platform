.PHONY: setup train serve test demo up stream down
setup:
	python -m pip install -r requirements.txt
train:
	python -m fraud.train --promote
serve:
	uvicorn fraud.api:app --host 127.0.0.1 --port 8000
test:
	python -m pytest -q
demo:
	python -m scripts.demo
up:
	docker compose up --build -d
stream:
	docker compose run --rm --no-deps producer
down:
	docker compose down
