from pathlib import Path
from typing import List
import re


def read_files_with_cignore(directory: str | Path) -> List[Path]:
    # Convert directory to a Path object
    directory = Path(directory)

    # Read the contents of the .cignore file
    cignore_path = directory / ".cignore"
    cignore_entries: List[str] = []
    if cignore_path.exists():
        cignore_entries = [
            line.strip()
            for line in cignore_path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    # Function to check if a file path should be ignored
    def is_ignored(file_path: Path) -> bool:
        for entry in cignore_entries:
            if re.match(entry, str(file_path)):
                return True
        return False

    # Recursively traverse the directory and collect file paths
    file_paths: List[str] = []
    for file_path in directory.rglob("*"):
        if file_path.is_file() and not is_ignored(file_path.relative_to(directory)):
            file_paths.append(file_path.relative_to(directory))

    return file_paths


def format_file_contents(file_paths: List[Path]) -> str:
    content = ""
    for file_path in file_paths:
        content += f"File: {file_path}\n"
        content += f"Contents:\n{file_path.read_text()}\n\n"
    return content


def main():
    directory = "."
    file_list = read_files_with_cignore(directory)
    print(file_list)
    # formatted_content = format_file_contents(file_list)
    # print(formatted_content)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    main()
