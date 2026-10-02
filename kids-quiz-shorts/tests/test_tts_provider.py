"""QUIZ_TTS_PROVIDER: Edge is the default, ElevenLabs is opt-in.

These tests never call a TTS service and never upload.
"""
import os
import unittest
from unittest import mock

import tts


class TtsProviderTests(unittest.TestCase):
    def test_default_is_edge_even_if_elevenlabs_key_is_set(self):
        env = {"ELEVENLABS_API_KEY": "sk_test", "ELEVENLABS_VOICE_ID": "voice"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("QUIZ_TTS_PROVIDER", None)
            self.assertEqual(tts.tts_provider(), "edge")
            names = [name for name, _fn in tts.engine_order()]
        self.assertEqual(names, ["edge", "silent"])
        self.assertNotIn("elevenlabs", names)

    def test_elevenlabs_is_opt_in(self):
        for raw in ("elevenlabs", "ElevenLabs", " eleven ", "11labs"):
            self.assertEqual(tts.tts_provider(raw), "elevenlabs", raw)
            names = [name for name, _fn in tts.engine_order(raw)]
            self.assertEqual(names[0], "elevenlabs", raw)
            self.assertIn("edge", names)

    def test_unknown_provider_stays_on_edge(self):
        self.assertEqual(tts.tts_provider("deepseek"), "edge")
        self.assertEqual(tts.tts_provider(""), "edge")
        self.assertEqual(tts.tts_provider("  "), "edge")


if __name__ == "__main__":
    unittest.main()
