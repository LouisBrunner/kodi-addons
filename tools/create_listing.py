import argparse
import os
import subprocess


def generate_html_for_folder(folder: str) -> None:
    index_page = "index.html"
    print(f"Generating HTML for {folder}")
    subprocess.run(
        [
            "tree",
            "-L",
            "1",
            "-T",
            os.path.basename(folder),
            "-H",
            "./",
            "--houtro",
            "",
            "--dirsfirst",
            "-s",
            "-D",
            "-I",
            index_page,
            "-o",
            index_page,
        ],
        cwd=folder,
    )
    for f in os.scandir(folder):
        if f.is_dir():
            generate_html_for_folder(f.path)


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
