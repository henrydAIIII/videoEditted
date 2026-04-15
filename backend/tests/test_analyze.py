import numpy as np

from pipeline.analyze import FrameSample, build_scenes, detect_change_points


def test_detect_change_points_and_build_scenes_from_samples():
    samples = [
        FrameSample(time_seconds=0.0, signature=np.zeros((2, 2)), change_score=1.0),
        FrameSample(time_seconds=1.0, signature=np.zeros((2, 2)), change_score=0.01),
        FrameSample(time_seconds=2.0, signature=np.zeros((2, 2)), change_score=0.02),
        FrameSample(time_seconds=3.0, signature=np.ones((2, 2)), change_score=0.95),
        FrameSample(time_seconds=4.0, signature=np.ones((2, 2)), change_score=0.02),
        FrameSample(time_seconds=5.0, signature=np.ones((2, 2)), change_score=0.01),
    ]

    change_points = detect_change_points(samples)

    assert change_points == [0, 3]

    scenes = build_scenes(samples, duration_seconds=6.0)

    assert len(scenes) == 2
    assert scenes[0]["start"] == "00:00:00.000"
    assert scenes[0]["end"] == "00:00:03.000"
    assert scenes[1]["start"] == "00:00:03.000"
    assert scenes[1]["end"] == "00:00:06.000"
