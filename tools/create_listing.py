import argparse
import os


def generate_html_for_folder(folder: str, show_parent: bool = False) -> None:
    index_page = "index.html"
    print(f"Generating HTML for {folder}")

    folders = []
    files = []
    for f in os.scandir(folder):
        filename = os.path.basename(f.path)
        if f.is_dir():
            generate_html_for_folder(f.path, show_parent=True)
            folders.append(filename)
        elif filename != index_page:
            files.append(filename)

    folder_name = os.path.basename(folder)
    with open(os.path.join(folder, index_page), "w") as f:
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
        for folder in folders:
            f.write(f'<li><a href="{folder}/">{folder}/</a></li>\n')
        for filename in files:
            f.write(f'<li><a href="{filename}">{filename}</a></li>\n')
        f.write("</body>\n")
        f.write("</html>\n")


def main():
    parser = argparse.ArgumentParser(description="Generate a HTML listing")
    parser.add_argument(
        "folder",
        type=str,
        help="The folder where to start listing files",
    )
    args = parser.parse_args()
    generate_html_for_folder(args.folder)


if __name__ == "__main__":
    main()
