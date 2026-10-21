"""Native compile of the F10 config read at the five-feature -O3 flags.

Requires Grimfeather Config.h via F10_CORE_NEW. Skips when that checkout
is absent. A pass is not a worldserver link and not gameplay acceptance.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / "src/Events/HallowsEndSoloFire.h").read_text()
CONFIG_CPP = ROOT / "src/Events/HallowsEndSoloFireConfig.cpp"
SHADE = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
CONFIG_TEXT = CONFIG_CPP.read_text()
STUB = ROOT / "tests/f10_s2_config_mgr_stub.cpp"
DRIVER = ROOT / "tests/f10_s2_config_marker_driver.cpp"

ENABLED_SYMBOL = (
    "NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireEnabledSetting()"
)
MULTIPLIER_SYMBOL = (
    "NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireMultiplierSetting()"
)
ENABLED_KEY = "NaxxramasCore.HallowsEnd.SoloFire.Enabled"
MULTIPLIER_KEY = "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier"


def config_header() -> Path | None:
    root = os.environ.get("F10_CORE_NEW")
    if not root:
        return None
    path = Path(root) / "src/common/Configuration/Config.h"
    if path.is_file():
        return path
    return None


def defined_symbols(path: Path) -> str:
    ran = subprocess.run(
        ["nm", "-C", "--defined-only", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return ran.stdout


class SoloFireConfigMarker(unittest.TestCase):
    def test_readers_are_declared_out_of_line_and_called_by_the_shade(self):
        self.assertIn("int32_t ReadHallowsEndSoloFireEnabledSetting();", HEADER)
        self.assertIn(
            "std::optional<int32_t> ReadHallowsEndSoloFireMultiplierSetting();",
            HEADER,
        )
        self.assertNotIn("inline int32_t ReadHallowsEndSoloFireEnabledSetting", HEADER)
        self.assertNotIn(
            "inline std::optional<int32_t> ReadHallowsEndSoloFireMultiplierSetting",
            HEADER,
        )
        self.assertNotIn("GetOption<", HEADER)
        self.assertEqual(CONFIG_TEXT.count("__attribute__((noinline))"), 3)
        self.assertEqual(CONFIG_TEXT.count("GetOption<std::string>"), 3)
        self.assertIn("EnabledConfigKey", CONFIG_TEXT)
        self.assertIn("MultiplierConfigKey", CONFIG_TEXT)
        self.assertIn("OneBucketConfigKey", CONFIG_TEXT)
        self.assertIn("ReadHallowsEndSoloFireOneBucketSetting()", CONFIG_TEXT)
        self.assertIn("EnabledFromRaw", CONFIG_TEXT)
        self.assertIn("MultiplierFromRaw", CONFIG_TEXT)
        self.assertIn("false);", CONFIG_TEXT)
        self.assertNotIn("namespace {", CONFIG_TEXT)
        self.assertEqual(SHADE.count(ENABLED_SYMBOL), 2)
        self.assertEqual(SHADE.count(MULTIPLIER_SYMBOL), 1)
        self.assertNotIn("GetOption<", SHADE)
        workflow = (ROOT / ".github/workflows/f10-s2-source-pin.yml").read_text()
        self.assertIn("cs02/f10-s2-shade-module-2026-10-20", workflow)
        self.assertIn("cs02/f10-s2-config-marker-2026-10-20", workflow)
        self.assertIn("src/Events/HallowsEndSoloFireConfig.cpp", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertIn("contents: read", workflow)

    def test_o3_object_archive_and_linked_binary_keep_the_readers(self):
        header = config_header()
        if header is None:
            self.skipTest("F10_CORE_NEW Config.h is not available")

        with tempfile.TemporaryDirectory(prefix="f10-config-marker-") as tmp:
            work = Path(tmp)
            obj = work / "config.o"
            archive = work / "libf10config.a"
            linked = work / "f10_config_marker"
            common = [
                "g++",
                "-std=gnu++20",
                "-O3",
                "-DNDEBUG",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-ffunction-sections",
                "-fdata-sections",
            ]
            compiled = subprocess.run(
                [
                    *common,
                    "-I",
                    str(header.parent),
                    "-I",
                    str(ROOT / "src/Events"),
                    "-c",
                    str(CONFIG_CPP),
                    "-o",
                    str(obj),
                ],
                capture_output=True,
                text=True,
            )
            if compiled.returncode != 0:
                self.fail(compiled.stderr)
            stub = subprocess.run(
                [
                    *common,
                    "-I",
                    str(header.parent),
                    "-c",
                    str(STUB),
                    "-o",
                    str(work / "stub.o"),
                ],
                capture_output=True,
                text=True,
            )
            if stub.returncode != 0:
                self.fail(stub.stderr)
            driver = subprocess.run(
                [
                    *common,
                    "-I",
                    str(ROOT / "src/Events"),
                    "-c",
                    str(DRIVER),
                    "-o",
                    str(work / "driver.o"),
                ],
                capture_output=True,
                text=True,
            )
            if driver.returncode != 0:
                self.fail(driver.stderr)

            subprocess.run(
                ["ar", "rcs", str(archive), str(obj)],
                check=True,
                capture_output=True,
                text=True,
            )
            linked_run = subprocess.run(
                [
                    "g++",
                    "-O3",
                    "-DNDEBUG",
                    "-Wl,--gc-sections",
                    str(work / "driver.o"),
                    str(work / "stub.o"),
                    str(archive),
                    "-o",
                    str(linked),
                ],
                capture_output=True,
                text=True,
            )
            if linked_run.returncode != 0:
                self.fail(linked_run.stderr)

            undefined = subprocess.run(
                ["nm", "-C", str(obj)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("ConfigMgr::GetOption<std::__cxx11::basic_string", undefined.stdout)

            for label, blob in (
                ("object", defined_symbols(obj)),
                ("archive", defined_symbols(archive)),
                ("linked", defined_symbols(linked)),
            ):
                self.assertIn(ENABLED_SYMBOL, blob, label)
                self.assertIn(MULTIPLIER_SYMBOL, blob, label)

            ran = subprocess.run(
                [str(linked)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(ran.returncode, 0, ran.stderr or ran.stdout)
            self.assertIn(f"KEY={ENABLED_KEY} DEF=0 LOGS=0", ran.stdout)
            self.assertIn(f"KEY={MULTIPLIER_KEY} DEF=3 LOGS=0", ran.stdout)
            self.assertIn("F10_CONFIG_MARKER_OK", ran.stdout)


if __name__ == "__main__":
    unittest.main()
