import zipfile

import make_release_zip


def test_release_folder_name_contains_version():
    assert make_release_zip.RELEASE_FOLDER_NAME.startswith("APE-v")
    assert make_release_zip.RELEASE_FOLDER_NAME.endswith("-portable")


def test_release_zip_verification_detects_ape_exe(tmp_path, monkeypatch):
    zip_path = tmp_path / "APE-vtest-portable.zip"
    folder_name = "APE-vtest-portable"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(f"{folder_name}/APE.exe", "placeholder")

    monkeypatch.setattr(make_release_zip, "RELEASE_ZIP_PATH", zip_path)
    monkeypatch.setattr(make_release_zip, "RELEASE_FOLDER_NAME", folder_name)

    make_release_zip.verify_zip()
