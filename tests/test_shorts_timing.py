from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from multiversal_pictures.files import ensure_dir, write_json
from multiversal_pictures.media import ffmpeg_executable, probe_media
from multiversal_pictures.narration import build_narration_plan, resolve_segment_stitch_seconds
from multiversal_pictures.stitching import stitch_run
from multiversal_pictures.subtitles import build_subtitle_plan
from multiversal_pictures.tts import _supports_speech_instructions


class ShortsTimingTests(unittest.TestCase):
    def test_compact_timing_defaults_and_override(self) -> None:
        shotlist = {
            "project": {
                "title": "Compact Timing",
                "narration_timing_mode": "compact",
            },
            "shots": [
                {
                    "id": "s1",
                    "title": "Shot One",
                    "seconds": "4",
                    "narration_line": "A short opening line.",
                },
                {
                    "id": "s2",
                    "title": "Shot Two",
                    "seconds": "4",
                    "narration_line": "An override line.",
                    "stitch_seconds": 3.8,
                },
            ],
        }
        plan = build_narration_plan(shotlist, default_offset_ms=None)

        first = plan["segments"][0]
        self.assertEqual(plan["narration_timing_mode"], "compact")
        self.assertEqual(first["narration_offset_ms"], 150)
        self.assertEqual(first["hold_after_narration_ms"], 250)
        self.assertEqual(resolve_segment_stitch_seconds(first, raw_duration_seconds=1.0, timing_mode="compact"), 1.6)
        self.assertEqual(resolve_segment_stitch_seconds(first, raw_duration_seconds=2.0, timing_mode="compact"), 2.4)

        second = plan["segments"][1]
        self.assertEqual(resolve_segment_stitch_seconds(second, raw_duration_seconds=0.9, timing_mode="compact"), 3.8)

    def test_locked_timing_uses_full_shot_length(self) -> None:
        shotlist = {
            "project": {"title": "Locked Timing"},
            "shots": [
                {
                    "id": "s1",
                    "title": "Locked Shot",
                    "seconds": "8",
                    "narration_line": "A calmer long-form line.",
                }
            ],
        }
        plan = build_narration_plan(shotlist, default_offset_ms=None)
        segment = plan["segments"][0]
        self.assertEqual(plan["narration_timing_mode"], "locked")
        self.assertEqual(segment["narration_offset_ms"], 500)
        self.assertEqual(resolve_segment_stitch_seconds(segment, raw_duration_seconds=1.2, timing_mode="locked"), 8.0)

    def test_instruction_gating_respects_model_capability(self) -> None:
        self.assertTrue(_supports_speech_instructions("gpt-4o-mini-tts"))
        self.assertTrue(_supports_speech_instructions("gpt-4o-mini-tts-2025-12-15"))
        self.assertFalse(_supports_speech_instructions("tts-1"))
        self.assertFalse(_supports_speech_instructions("tts-1-hd"))

    def test_subtitle_plan_uses_manifest_stitch_seconds(self) -> None:
        shotlist = {
            "project": {
                "title": "Subtitle Timing",
                "narration_timing_mode": "compact",
                "subtitle_layout": "vertical",
                "subtitle_position": "bottom_raised",
                "size": "1024x1792",
            },
            "shots": [
                {
                    "id": "s1",
                    "title": "Hook",
                    "seconds": "4",
                    "narration_line": "First line lands quickly.",
                    "narration_offset_ms": 150,
                },
                {
                    "id": "s2",
                    "title": "Proof",
                    "seconds": "4",
                    "narration_line": "Second line follows without dead air.",
                    "narration_offset_ms": 150,
                },
            ],
        }
        narration_manifest = {
            "timing_mode": "compact",
            "segments": [
                {"shot_id": "s1", "narration_offset_ms": 150, "raw_duration_seconds": 1.0, "stitch_seconds": 1.6},
                {"shot_id": "s2", "narration_offset_ms": 150, "raw_duration_seconds": 1.2, "stitch_seconds": 1.9},
            ],
        }

        plan = build_subtitle_plan(shotlist=shotlist, narration_manifest=narration_manifest, default_offset_ms=None)
        self.assertAlmostEqual(plan["duration_seconds"], 3.5, places=3)
        self.assertEqual(len(plan["cues"]), 2)
        self.assertAlmostEqual(plan["cues"][1]["start_seconds"], 1.75, places=2)

    def test_stitch_run_trims_video_to_compact_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            ensure_dir(run_dir / "narration")
            shots_dir = ensure_dir(run_dir / "shots")
            shot_one_path = shots_dir / "shot-one.mp4"
            shot_two_path = shots_dir / "shot-two.mp4"
            self._make_color_clip(shot_one_path, seconds=4.0, color="black")
            self._make_color_clip(shot_two_path, seconds=4.0, color="white")

            shotlist = {
                "project": {
                    "title": "Trimmed Stitch",
                    "narration_timing_mode": "compact",
                },
                "shots": [
                    {"id": "s1", "title": "One", "seconds": "4", "narration_line": "One."},
                    {"id": "s2", "title": "Two", "seconds": "4", "narration_line": "Two."},
                ],
            }
            run_manifest = {
                "shots": [
                    {
                        "id": "s1",
                        "status": "completed",
                        "downloads": [{"variant": "video", "path": str(shot_one_path)}],
                    },
                    {
                        "id": "s2",
                        "status": "completed",
                        "downloads": [{"variant": "video", "path": str(shot_two_path)}],
                    },
                ]
            }
            narration_manifest = {
                "timing_mode": "compact",
                "segments": [
                    {"shot_id": "s1", "stitch_seconds": 1.6},
                    {"shot_id": "s2", "stitch_seconds": 2.1},
                ],
            }

            write_json(run_dir / "shotlist.json", shotlist)
            write_json(run_dir / "run-manifest.json", run_manifest)
            write_json(run_dir / "narration" / "narration-manifest.json", narration_manifest)

            output_path = run_dir / "story.mp4"
            stitch_manifest = stitch_run(run_dir=run_dir, output_path=output_path, overwrite=True)
            info = probe_media(output_path)

            self.assertEqual(stitch_manifest["clip_count"], 2)
            self.assertAlmostEqual(info.duration_seconds or 0.0, 3.7, delta=0.25)

    def _make_color_clip(self, path: Path, *, seconds: float, color: str) -> None:
        ffmpeg = ffmpeg_executable()
        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x240:r=24",
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
        subprocess.run(command, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
