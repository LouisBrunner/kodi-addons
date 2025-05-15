import argparse
import os
import subprocess


def generate_html_for_folder(folder: str) -> None:
    print(f"Generating HTML for {folder}")
    subprocess.run(
        [
            "tree",
            "-L",
            "1",
            "-H",
            "./",
            "--houtro",
            "",
            "--dirsfirst",
            "-s",
            "-D",
            "-I",
            "index.html",
            "-o",
            "index.html",
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
