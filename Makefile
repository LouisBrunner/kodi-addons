ADDONS = plugin.video.dropout
OUT_FOLDER ?= out
DATADIR ?= $(OUT_FOLDER)/addons
OUT_REPO ?= $(OUT_FOLDER)/repo.zip

build:
	mkdir -p $(DATADIR)
	python3 vendor/create_repository.py $(ADDONS) --datadir $(DATADIR)
	zip -r $(OUT_REPO) repo
	python3 tools/create_listing.py out
.PHONY: build

serve:
	python3 -m http.server -d $(OUT_FOLDER)
.PHONY: serve

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
