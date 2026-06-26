"""Generate a HTML listing for a folder, used to build the Kodi addon repository."""

import argparse
import os
from pathlib import Path


def _generate_html_for_folder(folder: str, *, show_parent: bool = False) -> None:
    index_page = "index.html"
    print(f"Generating HTML for {folder}")

    folders = []
    files = []
    for f in os.scandir(folder):
        filename = Path(f.path).name
        if f.is_dir():
            _generate_html_for_folder(f.path, show_parent=True)
            folders.append(filename)
        elif filename != index_page:
            files.append(filename)

    folderp = Path(folder)
    folder_name = folderp.name
    with (folderp / index_page).open("w") as f:
        f.write("<!DOCTYPE html>\n")
        f.write('<html lang="en">\n')
        f.write("<head>\n")
        f.write(f"<title>{folder_name}</title>\n")
        f.write("</head>\n")
        f.write("<body>\n")
        f.write(f"<h1>{folder_name}</h1>\n")
        f.write("<ul>\n")
        if show_parent:
            f.write('<li><a href="..">..</a></li>\n')
        f.writelines(f'<li><a href="{fld}/">{fld}/</a></li>\n' for fld in folders)
        for filename in files:
            f.write(f'<li><a href="{filename}">{filename}</a></li>\n')
        f.write("</body>\n")
        f.write("</html>\n")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate a HTML listing")
    parser.add_argument(
        "folder",
        type=str,
        help="The folder where to start listing files",
    )
    args = parser.parse_args()
    _generate_html_for_folder(args.folder)


if __name__ == "__main__":
    _main()
