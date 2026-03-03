#!/usr/bin/env python3
"""
Live integration test: MacosWifiCollector → FeatureExtractor → Classifier.

Runs the full ADR-013 commodity sensing pipeline against a real macOS WiFi
interface using CoreWLAN (via the ``mac_wifi`` Swift helper) as the RSSI source.

Usage:
    python -m pytest v1/tests/integration/test_macos_live_sensing.py -v -o "addopts=" -s

Requirements:
    - macOS with Xcode Command Line Tools (swiftc)
    - Connected to a WiFi network
    - scipy, numpy installed
"""
import platform
import subprocess
import sys
import time

import pytest

_IS_MACOS = platform.system() == "Darwin"

# Plausible RSSI/noise bounds for live WiFi samples
_MIN_DBM = -120.0
_MAX_DBM = 0.0


def _swiftc_available() -> bool:
    """Return True if swiftc is on PATH (Xcode Command Line Tools installed)."""
    if not _IS_MACOS:
        return False
    try:
        result = subprocess.run(
            ["swiftc", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not (_IS_MACOS and _swiftc_available()),
    reason="Requires macOS with Xcode Command Line Tools (swiftc)",
)

from v1.src.sensing.rssi_collector import MacosWifiCollector, WifiSample
from v1.src.sensing.feature_extractor import RssiFeatureExtractor, RssiFeatures
from v1.src.sensing.classifier import PresenceClassifier, MotionLevel, SensingResult
from v1.src.sensing.backend import CommodityBackend, Capability


class TestMacosWifiCollectorLive:
    """Live tests against real macOS WiFi hardware via CoreWLAN."""

    def test_collector_starts_and_produces_samples(self):
        """Collector should start cleanly and buffer real RSSI samples."""
        collector = MacosWifiCollector(sample_rate_hz=5.0)
        collector.start()
        try:
            time.sleep(1.5)
            samples = collector.get_samples()
            assert len(samples) > 0, "Expected at least one sample after 1.5 seconds"
        finally:
            collector.stop()

    def test_sample_fields_are_valid(self):
        """Each WifiSample should have plausible RSSI and noise values."""
        collector = MacosWifiCollector(sample_rate_hz=5.0)
        collector.start()
        try:
            time.sleep(1.5)
            samples = collector.get_samples()
            assert len(samples) > 0
            for s in samples:
                assert isinstance(s, WifiSample)
                assert _MIN_DBM <= s.rssi_dbm <= _MAX_DBM, f"RSSI out of range: {s.rssi_dbm}"
                assert _MIN_DBM <= s.noise_dbm <= _MAX_DBM, f"Noise out of range: {s.noise_dbm}"
                assert 0.0 <= s.link_quality <= 1.0
                assert s.interface == "en0"
        finally:
            collector.stop()

    def test_feature_extraction_from_live_samples(self):
        """Feature extractor should produce valid features from live macOS samples."""
        collector = MacosWifiCollector(sample_rate_hz=5.0)
        extractor = RssiFeatureExtractor(window_seconds=10.0)

        collector.start()
        try:
            time.sleep(2.0)
            samples = collector.get_samples()
            assert len(samples) >= 4, f"Too few samples: {len(samples)}"

            features = extractor.extract(samples)
            assert features.n_samples >= 4
            assert _MIN_DBM <= features.mean <= _MAX_DBM
        finally:
            collector.stop()

    def test_full_pipeline_via_commodity_backend(self):
        """CommodityBackend with MacosWifiCollector should classify presence."""
        collector = MacosWifiCollector(sample_rate_hz=5.0)
        backend = CommodityBackend(
            collector=collector,
            extractor=RssiFeatureExtractor(window_seconds=10.0),
            classifier=PresenceClassifier(),
        )

        backend.start()
        try:
            time.sleep(2.5)
            result = backend.get_result()
            assert isinstance(result, SensingResult)
            assert isinstance(result.motion_level, MotionLevel)
            assert 0.0 <= result.confidence <= 1.0
        finally:
            backend.stop()

    def test_backend_capabilities_are_presence_and_motion(self):
        """MacosWifiCollector-backed CommodityBackend should only report PRESENCE/MOTION."""
        collector = MacosWifiCollector(sample_rate_hz=5.0)
        backend = CommodityBackend(collector=collector)

        caps = backend.get_capabilities()
        assert Capability.PRESENCE in caps
        assert Capability.MOTION in caps
        assert Capability.RESPIRATION not in caps
        assert Capability.POSE not in caps
