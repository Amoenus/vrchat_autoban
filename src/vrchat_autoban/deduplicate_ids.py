import argparse
from pathlib import Path

from vrchat_autoban.constants import DEFAULT_CRASHER_ID_DUMP_FILENAME


def deduplicate_and_trim_ids_in_file(file_path: Path):
    """
    Reads a file containing comma-separated IDs, potentially with newlines and extra whitespace.
    It trims whitespace from each ID, removes duplicates, sorts them,
    and overwrites the file with the cleaned, comma-separated list of unique IDs.
    """
    try:
        if not file_path.exists():
            print(f"Error: File '{file_path}' not found.")
            return

        # Read the entire content
        original_raw_content = file_path.read_text(encoding="utf-8")

        if not original_raw_content.strip():
            print(
                f"File '{file_path}' is empty or contains only whitespace. No changes needed."
            )
            return

        # 1. Replace newlines with nothing to handle multi-line comma-separated lists.
        # 2. Split by comma.
        # 3. Strip whitespace from each potential ID.
        # 4. Filter out any empty strings that might result from trailing commas or multiple commas.
        ids_list = [
            id_str.strip()
            for id_str in original_raw_content.replace("\n", "").split(",")
            if id_str.strip()  # Ensures empty strings after split (e.g., from "id1,,id2" or "id1,") are removed
        ]

        original_count = len(ids_list)

        # Deduplicate using a set and then convert back to a list and sort for consistent output
        unique_ids_list = sorted(list(set(ids_list)))
        new_count = len(unique_ids_list)

        # Reconstruct the cleaned content
        new_content = ",".join(unique_ids_list)

        # Check if changes were actually made to avoid unnecessary file write.
        # `original_cleaned_content` represents what the file *would* look like if it only had its original IDs
        # deduplicated and sorted, without other formatting changes.
        # This is mainly for the early exit logic.
        original_cleaned_content_for_comparison = ",".join(sorted(list(set(ids_list))))

        # Early exit if the file content, when stripped of leading/trailing whitespace (like a final newline),
        # already matches the new_content.
        if (
            original_cleaned_content_for_comparison.strip() == new_content.strip()
            and original_raw_content.strip() == new_content.strip()
        ):
            print(
                f"File '{file_path}' already contains unique, trimmed, and sorted IDs in the standard format. No changes made."
            )
            print(f"  ID count: {new_count}")
            return

        # Write the cleaned content back to the file
        file_path.write_text(new_content, encoding="utf-8")

        print(f"Successfully processed '{file_path}':")
        print(
            f"  Original ID count (after splitting and initial trim): {original_count}"
        )
        print(f"  Unique ID count: {new_count}")
        removed_count = original_count - new_count
        print(f"  Number of duplicates/empty entries removed: {removed_count}")

        # Corrected final message logic:
        if removed_count > 0:
            print(
                "  File content has been replaced with unique, trimmed, and sorted IDs."
            )
        # Compare the initially parsed list (before sorting and unique) with the final content.
        # If counts are same but content differs, it means resorting or minor reformatting of already unique items.
        elif ",".join(ids_list) != new_content:
            print(
                "  File content was already unique but has been re-sorted and/or reformatted to the standard."
            )
        else:
            # This implies the content was effectively the same as new_content already,
            # but the raw file might have had subtle differences (e.g., a final newline)
            # that caused the early exit condition based on raw_original_content.strip() to not match.
            print(
                "  File content has been re-saved in the standard format (e.g., ensuring no trailing newlines or standard comma spacing)."
            )

    except Exception as e:
        print(f"An unexpected error occurred while processing '{file_path}': {e}")


if __name__ == "__main__":
    # The base directory for data files, consistent with main.py's assumptions
    # This assumes the script is in src/vrchat_autoban/
    source_base_dir = Path(__file__).resolve().parent
    default_file_path = source_base_dir / DEFAULT_CRASHER_ID_DUMP_FILENAME

    parser = argparse.ArgumentParser(
        description="Deduplicates and trims user IDs in a comma-separated text file. Overwrites the file."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=default_file_path,
        help=(
            "Path to the text file containing comma-separated user IDs. "
            f"(Default: {default_file_path})"
        ),
    )
    args = parser.parse_args()

    print(f"Attempting to process file: {args.file.resolve()}")
    deduplicate_and_trim_ids_in_file(args.file)
