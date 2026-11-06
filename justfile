set lazy

out := "out"
out-addons := f"{{ out }}/addons"
addons := `ls -d plugin.*`
just := just_executable()

all: build

build: && (_build_html_listings out)
    mkdir -p {{ out-addons }}
    python3 vendor/create_repository.py {{ addons }} --datadir {{ out-addons }}
    zip -r {{ out }}/repo.zip repo

serve:
    python3 -m http.server -d $(OUT_FOLDER)

setup:
    uv sync --all-packages

dev target host="root@libreelec.local":
    hot -d {{ target }} {{ just }} deploy {{ target }} {{ host }}

format:
    uv run ruff format

vet:
    uv run ruff check

deploy target host: clean
    scp -r {{ target }}/. {{ host }}:/storage/.kodi/addons/{{ target }}

test target=addons:
    uv run --all-packages pytest {{ target }}

clean:
    rm -rf {{ out }}
    find {{ addons }} -type f -name "*.pyc" -delete
    find {{ addons }} -type d -name "__pycache__" -o -name ".ruff_cache" -o -name ".pytest_cache" -o -name ".venv" -exec rm -rf {} +

[private]
[script("python3")]
_build_html_listings target:
    import argparse
    import os
    from pathlib import Path

    index_page = "index.html"

    def _gen(folder: Path, *, show_parent: bool = False) -> None:
      print(f"Generating HTML for {folder}")

      folders = []
      files = []
      for f in folder.iterdir():
          filename = f.name
          if f.is_dir():
              _gen(f, show_parent=True)
              folders.append(filename)
          elif filename != index_page:
              files.append(filename)

      with (folder / index_page).open("w") as f:
          f.write('<!DOCTYPE html><html lang="en">')
          f.write(f"<head><title>{folder.name}</title></head>")
          f.write(f"<body><h1>{folder.name}</h1><ul>")
          if show_parent:
              f.write('<li><a href="..">..</a></li>')
          f.writelines(f'<li><a href="{fld}/">{fld}/</a></li>' for fld in folders)
          f.writelines(f'<li><a href="{file}">{file}</a></li>' for file in files)
          f.write("</ul></body></html>")

    _gen(Path("{{ target }}"))
