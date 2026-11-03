#!/usr/bin/env python3
"""
Unit tests for Milestone 2 PoC tools:
  - cellular_dataflow_tracer.py
  - dynamic_carrier_bypass_poc.py
"""

import os
import shutil
import tempfile
import unittest

from cellular_dataflow_tracer import (
    SimulatedCellularEntry,
    SimulatedStatusBarData,
    simulate_downstream_collision
)
from dynamic_carrier_bypass_poc import (
    generate_mdm_carrier_profile,
    audit_mdm_carrier_schema,
    evaluate_wireless_domain_safety,
    evaluate_carrier_bundle_signature_check,
    generate_sentinel_matrix_archives
)


class TestMilestone2PoC(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_downstream_overlay_monolithic_replacement(self):
        live_entry = SimulatedCellularEntry(
            enabled=True,
            status=5,
            display_value=3,
            network_type=9,
            carrier_string="LiveNetwork"
        )
        overlay_entry = SimulatedCellularEntry(
            enabled=True,
            status=5,
            display_value=4,
            network_type=10,
            carrier_string="CustomName"
        )

        live_data = SimulatedStatusBarData(live_entry)
        overlay_data = SimulatedStatusBarData(overlay_entry)
        merged = live_data.apply_overlay(overlay_data)

        # Verification: Monolithic replacement overwrote live bars and live type
        self.assertEqual(merged.cellular_entry.carrier_string, "CustomName")
        self.assertEqual(merged.cellular_entry.display_value, 4)
        self.assertEqual(merged.cellular_entry.network_type, 10)

    def test_collision_simulation_omit_display_value(self):
        sim = simulate_downstream_collision(
            live_bars=3,
            live_type=10,
            override_carrier="Apple 5G",
            omit_display_value=True
        )
        # Omission of displayValue results in 0 lit bars (4 dimmed hollow bars)
        self.assertEqual(sim["rendered_bars"], 0)
        self.assertEqual(sim["bars_behavior"], "FROZEN_TO_ZERO (Hollow Gray)")
        self.assertFalse(sim["live_signal_passed_through"])

    def test_mdm_profile_generation(self):
        profile_path = os.path.join(self.temp_dir, "test.mobileconfig")
        raw_bytes = generate_mdm_carrier_profile(
            carrier_name_override="TestCarrier",
            output_path=profile_path
        )
        self.assertGreater(len(raw_bytes), 100)
        self.assertTrue(os.path.exists(profile_path))
        self.assertIn(b"com.apple.cellular", raw_bytes)
        self.assertIn(b"TestCarrier", raw_bytes)

    def test_audit_schemas_and_safety(self):
        mdm_audit = audit_mdm_carrier_schema()
        self.assertEqual(mdm_audit["verdict"], "UNSUPPORTED")

        wireless_audit = evaluate_wireless_domain_safety()
        self.assertEqual(wireless_audit["safety_verdict"], "CRITICAL_HAZARD")
        self.assertFalse(wireless_audit["feasible_non_jailbreak"])

        cb_audit = evaluate_carrier_bundle_signature_check()
        self.assertEqual(cb_audit["verdict"], "EXPERIMENTALLY_BLOCKED")

    def test_sentinel_matrix_generation(self):
        manifest = generate_sentinel_matrix_archives(self.temp_dir)
        self.assertEqual(len(manifest), 3)
        for item in manifest:
            self.assertTrue(os.path.exists(item["file"]))
            self.assertGreater(os.path.getsize(item["file"]), 200)


if __name__ == "__main__":
    unittest.main()
