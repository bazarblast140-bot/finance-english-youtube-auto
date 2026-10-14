"""Gemini TTS provider — fully mocked, no network, no real keys."""
import base64
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tts  # noqa: E402

ENVS = ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3")


def _resp(status, pcm=None):
    r = mock.Mock(status_code=status, text="err")
    if pcm is not None:
        r.json.return_value = {"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000",
            "data": base64.b64encode(pcm).decode()}}]}}]}
    return r


PCM = struct.pack("<h", 1000) * 24000  # 1 second of 24 kHz s16le


class GeminiTests(unittest.TestCase):
    def setUp(self):
        tts._gemini_dead.clear()
        self.tmp = Path(tempfile.mkdtemp()) / "x.wav"

    def env(self, **kv):
        base = {k: "" for k in ENVS}
        base.update(kv)
        return mock.patch.dict(os.environ, base, clear=False)

    def test_chain_order(self):
        self.assertEqual(tts.tts_provider(" Gemini "), "gemini")
        self.assertEqual([n for n, _ in tts.engine_order("gemini")],
                         ["gemini", "elevenlabs", "edge", "silent"])
        self.assertEqual([n for n, _ in tts.engine_order("edge")], ["edge", "silent"])

    def test_keys_skip_missing_and_empty(self):
        with self.env(GEMINI_API_KEY_2="k2", GEMINI_API_KEY_3="k3"):
            os.environ.pop("GEMINI_API_KEY", None)
            self.assertEqual(tts.gemini_keys(), ["k2", "k3"])
        with self.env(GEMINI_API_KEY="  ", GEMINI_API_KEY_3="k3"):
            self.assertEqual(tts.gemini_keys(), ["k3"])
        with self.env():
            self.assertEqual(tts.gemini_keys(), [])
            self.assertFalse(tts._gemini("नमस्ते", self.tmp))

    def test_rotates_on_429_and_403_and_converts_pcm(self):
        calls = []

        def post(url, json, timeout, headers):
            calls.append(headers["x-goog-api-key"])
            return {"k1": _resp(429), "k2": _resp(403), "k3": _resp(200, PCM)}[calls[-1]]

        with self.env(GEMINI_API_KEY="k1", GEMINI_API_KEY_2="k2", GEMINI_API_KEY_3="k3"), \
                mock.patch("requests.post", side_effect=post):
            self.assertTrue(tts._gemini("नमस्ते", self.tmp))
        self.assertEqual(calls, ["k1", "k2", "k3"])
        self.assertAlmostEqual(tts.audio_duration(self.tmp), 1.0, delta=0.05)

    def test_all_keys_fail_returns_false(self):
        with self.env(GEMINI_API_KEY_2="k2", GEMINI_API_KEY_3="k3"), \
                mock.patch("requests.post", return_value=_resp(429)):
            self.assertFalse(tts._gemini("नमस्ते", self.tmp))

    def test_other_error_and_bad_body_fall_back(self):
        with self.env(GEMINI_API_KEY_2="k2"), \
                mock.patch("requests.post", return_value=_resp(500)):
            self.assertFalse(tts._gemini("नमस्ते", self.tmp))
        bad = _resp(200)
        bad.json.return_value = {"candidates": []}
        with self.env(GEMINI_API_KEY_2="k2"), mock.patch("requests.post", return_value=bad):
            self.assertFalse(tts._gemini("नमस्ते", self.tmp))

    def test_empty_audio_retried_once_on_same_key(self):
        bad = _resp(200)
        bad.json.return_value = {"candidates": [{"finishReason": "OTHER"}]}
        with self.env(GEMINI_API_KEY_2="k2"), \
                mock.patch("requests.post", side_effect=[bad, _resp(200, PCM)]) as p:
            self.assertTrue(tts._gemini("नमस्ते", self.tmp))
        self.assertEqual(p.call_count, 2)

    def test_say_falls_through_to_next_engine(self):
        fake = lambda t, p: (tts._silent(t, p))  # noqa: E731
        order = (("gemini", lambda t, p: False), ("elevenlabs", lambda t, p: False),
                 ("edge", fake))
        with mock.patch.object(tts, "engine_order", return_value=order), \
                mock.patch.object(tts, "CACHE", self.tmp.parent), \
                mock.patch.dict(os.environ, {"QUIZ_TTS_PROVIDER": "gemini"}):
            _p, d, eng = tts.say("एक दो तीन", "t")
        self.assertEqual(eng, "edge")
        self.assertGreater(d, 1)


if __name__ == "__main__":
    unittest.main()
