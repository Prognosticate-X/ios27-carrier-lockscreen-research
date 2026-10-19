#!/usr/bin/env python3
"""Comprehensive test suite for iOS 27 AirLift upgrades."""

import unittest
import tempfile
from pathlib import Path
from display_metrics import get_visual_width, check_dynamic_island_overflow
from presets import load_all_presets, get_preset, save_preset, BUILTIN_PRESETS
from generate_statusbar_archive import build_cellular_archive, inspect_archive
from footnote_generator import generate_footnote_profile
from terminal_preview import render_terminal_preview


class TestAirliftFeatures(unittest.TestCase):
    def test_visual_width_ascii(self):
        self.assertEqual(get_visual_width("Carrier"), 7)
        self.assertEqual(get_visual_width("5G"), 2)

    def test_visual_width_cjk_emoji(self):
        self.assertEqual(get_visual_width("中国移动"), 8)
        self.assertEqual(get_visual_width("中国移动 5G"), 11)
        self.assertEqual(get_visual_width(""), 2)
        self.assertEqual(get_visual_width("★"), 2)

    def test_dynamic_island_overflow_heuristics(self):
        res_safe = check_dynamic_island_overflow("移动 5G", is_dynamic_island=True)
        self.assertFalse(res_safe.is_overflow_risk)

        res_long = check_dynamic_island_overflow("中国广电超级极速融合宽频网络 5G", is_dynamic_island=True)
        self.assertTrue(res_long.is_overflow_risk)
        self.assertIn("Visual width", res_long.warning_message)

    def test_presets_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_file = Path(tmpdir) / "test_presets.json"
            all_presets = load_all_presets(preset_file)
            self.assertIn("cmcc-5g", all_presets)

            custom_cfg = {"carrier": "Custom 5G", "bars": 3, "type": "5g"}
            save_preset("my-test-preset", custom_cfg, preset_file)
            loaded = get_preset("my-test-preset", preset_file)
            self.assertEqual(loaded["carrier"], "Custom 5G")
            self.assertEqual(loaded["bars"], 3)

    def test_binary_archive_generation_single_and_dual(self):
        payload_single = build_cellular_archive(primary_carrier="Test Single", primary_bars=4)
        self.assertTrue(len(payload_single) > 500)
        self.assertTrue(payload_single.startswith(b"bplist00"))

        payload_dual = build_cellular_archive(
            primary_carrier="Primary", primary_badge="P",
            secondary_carrier="Secondary", secondary_badge="S"
        )
        self.assertTrue(len(payload_dual) > len(payload_single))

        payload_reset = build_cellular_archive(is_reset=True)
        self.assertTrue(len(payload_reset) < len(payload_single))

    def test_partial_archive_keeps_live_fields(self):
        """Partial mode must drop displayValue/type while keeping name + registration."""
        import plistlib

        from airlift_carrier_deploy import build_cellular_archive

        payload = build_cellular_archive(primary_carrier="Partial", partial=True)
        plist = plistlib.loads(payload)
        objects = plist["$objects"]

        def resolve(value):
            return objects[value.data] if isinstance(value, plistlib.UID) else value

        record = resolve(plist["$top"]["root"])
        data = resolve(record["statusBarData"])
        entry = resolve(data["cellularEntry"])
        self.assertNotIn("displayValue", entry)
        self.assertNotIn("type", entry)
        self.assertEqual(resolve(entry["string"]), "Partial")
        self.assertTrue(entry["enabled"])
        self.assertEqual(entry["status"], 5)

    def test_footnote_generator(self):
        data = generate_footnote_profile("Test Footnote Text")
        self.assertIn(b"com.apple.shareddeviceconfiguration", data)
        self.assertIn(b"Test Footnote Text", data)

    def test_terminal_preview(self):
        out = render_terminal_preview("TestCarrier", badge="P", bars=4)
        self.assertIn("Dynamic Island", out)
        self.assertIn("TestCarrier", out)


class TestPipelineDiagnostics(unittest.TestCase):
    """Regression coverage for the AirLift staging diagnostics added for iOS 27."""

    def test_describe_stage_failure_maps_flags(self):
        from airlift_carrier_deploy import describe_stage_failure

        self.assertIn(
            "Books preimage changed",
            describe_stage_failure({"booksPreimageStable": False}),
        )
        self.assertIn(
            "did not appear",
            describe_stage_failure({"sourceObjectsPresent": 0}),
        )
        self.assertIn(
            "zipServiceStatus=5",
            describe_stage_failure({"zipServiceStatus": 5}),
        )
        self.assertEqual(
            describe_stage_failure({}), "no diagnostic flag was reported"
        )

    def test_build_cleaned_books_snapshot(self):
        import plistlib
        import tempfile

        from airlift_carrier_deploy import build_cleaned_books_snapshot

        staging_row = {
            "Persistent ID": "../../airlift-src-" + "a" * 20 + "/payload",
            "Item ID": "1",
            "DSID": "1",
        }
        real_row = {"Persistent ID": "real-book-42", "Item ID": "2", "DSID": "1"}

        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "snapshot"
            cleaned = Path(tmp) / "cleaned"
            snapshot.mkdir()
            (snapshot / "file-0.bin").write_bytes(
                plistlib.dumps({"Books": [staging_row, real_row]}, fmt=plistlib.FMT_BINARY)
            )
            (snapshot / "file-1.bin").write_bytes(
                plistlib.dumps({"Books": [staging_row]}, fmt=plistlib.FMT_BINARY)
            )
            manifest = {
                "version": 1,
                "files": {
                    "Books/Books.plist": {
                        "exists": True,
                        "localName": "file-0.bin",
                        "size": 1,
                    },
                    "Books/Sync/Books.plist": {
                        "exists": True,
                        "localName": "file-1.bin",
                        "size": 1,
                    },
                },
                "directories": {},
            }
            (snapshot / "manifest.plist").write_bytes(
                plistlib.dumps(manifest, fmt=plistlib.FMT_BINARY)
            )

            report = build_cleaned_books_snapshot(snapshot, cleaned)

            self.assertEqual(report["droppedFiles"], ["Books/Sync/Books.plist"])
            self.assertEqual(report["filteredFiles"], ["Books/Books.plist"])
            cleaned_manifest = plistlib.loads((cleaned / "manifest.plist").read_bytes())
            self.assertFalse(
                cleaned_manifest["files"]["Books/Sync/Books.plist"]["exists"]
            )
            kept = plistlib.loads((cleaned / "file-0.bin").read_bytes())
            self.assertEqual(
                [row["Persistent ID"] for row in kept["Books"]], ["real-book-42"]
            )

    def test_parse_springboard_pid(self):
        from airlift_carrier_deploy import parse_springboard_pid

        table = (
            "PID   Executable Path\n"
            "---   --------------------------------------------------------\n"
            "37    /System/Library/CoreServices/SpringBoard.app/SpringBoard\n"
        )
        self.assertEqual(parse_springboard_pid(table), 37)
        self.assertIsNone(parse_springboard_pid("PID   Executable Path\n"))
        self.assertIsNone(parse_springboard_pid("12    /usr/libexec/otherd\n"))

    def test_dashboard_endpoints_return_json(self):
        """Regression: unknown endpoints must answer with JSON, never an empty body."""
        import http.client
        import json
        import threading
        from http.server import HTTPServer

        from gui_server import DashboardHandler

        server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            page = _http_request(port, "GET", "/")
            self.assertIn("btnRespring", page)
            self.assertIn("t_fn5", page)

            for method, path, expected in (
                ("POST", "/api/does-not-exist", 404),
                ("GET", "/definitely-not-here", 404),
            ):
                status, body = _http_request(port, method, path, raw=True)
                self.assertEqual(status, expected)
                self.assertTrue(
                    json.loads(body).get("error"),
                    f"{method} {path} must return a JSON error body, got {body!r}",
                )
        finally:
            server.shutdown()

class TestCommCenterPreferenceInjection(unittest.TestCase):
    """Offline coverage for the upstream CommCenter preference injector."""

    def test_operator_plist_payload(self):
        import plistlib

        from commcenter_carrier_inject import build_operator_plist

        payload = build_operator_plist(
            "UnicomDyn", ["46001", "46006"], include_carrier_name=True
        )
        self.assertTrue(payload.startswith(b"bplist00"))
        decoded = plistlib.loads(payload)
        self.assertEqual(
            decoded["InterCarrierRoamingDisplayNames"],
            {"46001": "UnicomDyn", "46006": "UnicomDyn"},
        )
        self.assertEqual(decoded["CarrierName"], "UnicomDyn")

    def test_operator_plist_requires_plmn(self):
        from airlift_carrier_deploy import AirLiftCarrierError
        from commcenter_carrier_inject import build_operator_plist

        with self.assertRaises(AirLiftCarrierError):
            build_operator_plist("X", [])

    def test_staging_zip_is_restricted_to_preferences(self):
        import io
        import zipfile

        from airlift_carrier_deploy import AirLiftCarrierError
        from commcenter_carrier_inject import PREFERENCE_DIR, build_staging_zip

        with self.assertRaises(AirLiftCarrierError):
            build_staging_zip("/var/mobile/Library/SpringBoard", b"payload")
        with self.assertRaises(AirLiftCarrierError):
            build_staging_zip("var/mobile/Library/Preferences", b"payload")
        with self.assertRaises(AirLiftCarrierError):
            build_staging_zip(PREFERENCE_DIR, b"")

        archive = zipfile.ZipFile(io.BytesIO(build_staging_zip(PREFERENCE_DIR, b"abc")))
        self.assertEqual(
            archive.read("p0/p1/p2/link"),
            b"../../../var/mobile/Library/Preferences",
        )
        self.assertEqual(archive.read("payload"), b"abc")

    def test_deploy_preference_rejects_unknown_domain(self):
        from airlift_carrier_deploy import AirLiftCarrierError
        from commcenter_carrier_inject import deploy_preference

        with self.assertRaises(AirLiftCarrierError):
            deploy_preference("udid-unused", "com.apple.springboard.plist", b"x")


class TestDevicePathProbe(unittest.TestCase):
    """Offline coverage for the read-only device path probe."""

    def test_allowlist(self):
        from airlift_carrier_deploy import AirLiftCarrierError
        from device_path_probe import validate_remote_path

        self.assertEqual(
            validate_remote_path("/var/mobile/Library/Preferences/com.apple.a.plist"),
            "/var/mobile/Library/Preferences/com.apple.a.plist",
        )
        self.assertEqual(
            validate_remote_path("/var/mobile/Library/Preferences/"),
            "/var/mobile/Library/Preferences",
        )
        for rejected in (
            "/var/mobile/Library/SpringBoardX/a",
            "/var/preferences/../../etc/passwd",
            "var/mobile/Library/Preferences/a.plist",
        ):
            with self.assertRaises(AirLiftCarrierError):
                validate_remote_path(rejected)

    def test_probe_zip_symlink_target(self):
        import io
        import zipfile

        from device_path_probe import build_probe_zip

        archive = zipfile.ZipFile(
            io.BytesIO(build_probe_zip("/var/mobile/Library/Preferences", b"probe"))
        )
        self.assertEqual(
            archive.read("p0/p1/p2/link"),
            b"../../../var/mobile/Library/Preferences",
        )



def _http_request(port, method, path, raw=False):
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        return (response.status, body) if raw else body
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()