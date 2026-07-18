"""Create a clean portable ZIP release from the PyInstaller build output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys
import zipfile

from ape.core.version import APP_CODE, VERSION

ROOT_DIR = Path(__file__).resolve().parent
DIST_APP_DIR = ROOT_DIR / "dist" / APP_CODE
RELEASES_DIR = ROOT_DIR / "releases"
RELEASE_FOLDER_NAME = f"{APP_CODE}-v{VERSION}-portable"
RELEASE_STAGING_DIR = RELEASES_DIR / RELEASE_FOLDER_NAME
RELEASE_ZIP_PATH = RELEASES_DIR / f"{RELEASE_FOLDER_NAME}.zip"

REQUIRED_FILES = [
    DIST_APP_DIR / f"{APP_CODE}.exe",
]
OPTIONAL_DOCS = [
    ROOT_DIR / "README_FOR_USERS.md",
    ROOT_DIR / "RELEASE_QA_CHECKLIST.md",
    ROOT_DIR / "CHANGELOG.md",
    ROOT_DIR / "PACKAGING.md",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def ensure_build_exists() -> None:
    if not DIST_APP_DIR.exists():
        fail(
            "Chưa thấy thư mục dist\\APE. Hãy chạy build_windows.bat trước."
        )
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        joined = "\n".join(str(path) for path in missing)
        fail(f"Thiếu file build bắt buộc:\n{joined}")


def clean_staging() -> None:
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    if RELEASE_STAGING_DIR.exists():
        shutil.rmtree(RELEASE_STAGING_DIR)
    if RELEASE_ZIP_PATH.exists():
        RELEASE_ZIP_PATH.unlink()


def copy_release_files() -> None:
    shutil.copytree(DIST_APP_DIR, RELEASE_STAGING_DIR)
    docs_dir = RELEASE_STAGING_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    for document in OPTIONAL_DOCS:
        if document.exists():
            shutil.copy2(document, docs_dir / document.name)

    launch_note = RELEASE_STAGING_DIR / "HUONG_DAN_NHANH.txt"
    launch_note.write_text(
        "APE - Adaptive Prediction Engine\n"
        f"Phien ban: {VERSION}\n\n"
        "Cach chay:\n"
        "1. Mo thu muc nay.\n"
        "2. Bam dup vao APE.exe.\n"
        "3. Neu Windows hoi bao mat, chon More info > Run anyway.\n\n"
        "Luu y:\n"
        "- Khong copy rieng APE.exe ra ngoai.\n"
        "- Hay giu nguyen ca thu muc release nay.\n"
        "- Du lieu SQLite nam trong thu muc data sau khi app tao/chay.\n",
        encoding="utf-8",
    )

    manifest = RELEASE_STAGING_DIR / "release_manifest.txt"
    manifest.write_text(
        f"app={APP_CODE}\n"
        f"version={VERSION}\n"
        f"created_at={datetime.now().isoformat(timespec='seconds')}\n"
        f"source_folder={DIST_APP_DIR}\n",
        encoding="utf-8",
    )


def create_zip() -> None:
    with zipfile.ZipFile(RELEASE_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in RELEASE_STAGING_DIR.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(RELEASES_DIR))


def verify_zip() -> None:
    if not RELEASE_ZIP_PATH.exists():
        fail("Không tạo được file ZIP.")
    with zipfile.ZipFile(RELEASE_ZIP_PATH, "r") as archive:
        names = set(archive.namelist())
    required_name = f"{RELEASE_FOLDER_NAME}/{APP_CODE}.exe"
    if required_name not in names:
        fail(f"ZIP thiếu {required_name}")


def main() -> int:
    ensure_build_exists()
    clean_staging()
    copy_release_files()
    create_zip()
    verify_zip()

    print("===============================================")
    print("APE release ZIP created successfully")
    print("===============================================")
    print(f"Folder: {RELEASE_STAGING_DIR}")
    print(f"ZIP   : {RELEASE_ZIP_PATH}")
    print(f"Size  : {RELEASE_ZIP_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
