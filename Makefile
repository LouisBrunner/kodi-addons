ADDONS = plugin.video.dropout
DATADIR ?= repo/addons
OUT_REPO ?= repo.zip

build:
	python3 vendor/create_repository.py $(ADDONS) --datadir $(DATADIR)
	zip -r $(OUT_REPO) repo
.PHONY: build

DEV_TARGET ?= plugin.video.dropout
KODI_HOST ?= root@libreelec.local

dev:
	fswatch $(DEV_TARGET) --one-per-batch --recursive --latency 1 --verbose | xargs -I{} make deploy
.PHONY: dev

deploy: clean
	scp -r $(DEV_TARGET)/. $(KODI_HOST):/storage/.kodi/addons/$(DEV_TARGET)
.PHONY: deploy

clean:
	find $(DEV_TARGET) -type f -name "*.pyc" -delete
.PHONY: clean
