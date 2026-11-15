"""Restore large checkpoint models from verified chunks (Python standard library)."""
import argparse
import hashlib
import json
from pathlib import Path


def child(root, name):
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Path leaves checkpoint directory")
    return result


def restore(asset):
    asset = Path(asset).resolve()
    manifest_path = asset / "large-files.json"
    if not manifest_path.exists():
        print("No split files:", asset)
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        target = child(asset, entry["path"])
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
                print("Already restored:", entry["path"])
                continue
            raise ValueError("Existing target differs: " + str(target))
        parts = []
        digest = hashlib.sha256()
        size = 0
        for part in entry["parts"]:
            data = child(asset, part["path"]).read_bytes()
            if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError("Corrupt chunk: " + part["path"])
            parts.append(data)
            digest.update(data)
            size += len(data)
        if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
            raise ValueError("Restored checksum differs: " + entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            for data in parts:
                output.write(data)
        print("RESTORED", entry["path"], size, entry["sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", required=True)
    restore(parser.parse_args().asset_dir)
