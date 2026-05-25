"""Download the BioSNAP ChG-Target Decagon dataset into ./data."""

from pathlib import Path

import requests

URL = (
    "http://snap.stanford.edu/biodata/datasets/10015/files/"
    "ChG-TargetDecagon_targets.csv.gz"
)
DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = DATA_DIR / "ChG-TargetDecagon_targets.csv.gz"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(URL, stream=True, timeout=60)
        response.raise_for_status()

        with open(OUTPUT_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"Success: saved dataset to {OUTPUT_FILE}")
    except requests.RequestException as e:
        print(f"Failure: could not download dataset — {e}")
    except OSError as e:
        print(f"Failure: could not write file to {OUTPUT_FILE} — {e}")


if __name__ == "__main__":
    main()
