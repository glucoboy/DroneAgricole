import struct
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

import numpy as np
from rosbags.typesys import Stores, get_typestore

from drone_agricole_dataset_adapter.botanicgarden import (
    LIVOX2_CUSTOM_MSG_TYPE,
    PIPELINE_TOPICS,
    _convert_livox_custom_message,
    _normalize_velodyne_point_times,
    _register_livox2_types,
    load_config,
)


class BotanicGardenConfigTest(TestCase):
    def test_expected_pipeline_topics_are_separate(self) -> None:
        self.assertEqual(
            set(PIPELINE_TOPICS["velodyne_xsens"]),
            {"/velodyne_points", "/imu/data", "/gt_poses"},
        )
        self.assertEqual(
            set(PIPELINE_TOPICS["livox_bmi088"]),
            {"/livox/lidar", "/livox/imu", "/gt_poses"},
        )

    def test_wrong_dataset_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("dataset: another_dataset\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_velodyne_times_become_start_relative(self) -> None:
        data = np.frombuffer(
            bytearray(struct.pack("<fff", -0.1, 0.0, 0.1)),
            dtype=np.uint8,
        )
        message = SimpleNamespace(
            fields=[SimpleNamespace(name="time", offset=0, datatype=7, count=1)],
            point_step=4,
            row_step=12,
            width=3,
            height=1,
            is_bigendian=False,
            data=data,
            header=SimpleNamespace(
                stamp=SimpleNamespace(sec=10, nanosec=0),
            ),
        )

        result = _normalize_velodyne_point_times(message)
        normalized = np.frombuffer(message.data, dtype="<f4")

        np.testing.assert_allclose(normalized, [0.0, 0.1, 0.2], atol=1e-7)
        self.assertAlmostEqual(float(result["header_shift_s"]), -0.1)
        self.assertEqual(message.header.stamp.sec, 9)
        self.assertLessEqual(abs(message.header.stamp.nanosec - 900_000_000), 1)

    def test_livox_custom_message_is_migrated_to_driver2(self) -> None:
        typestore = get_typestore(Stores.ROS2_HUMBLE)
        _register_livox2_types(typestore)
        source = SimpleNamespace(
            header=SimpleNamespace(
                stamp=SimpleNamespace(sec=123, nanosec=456),
                frame_id="livox_frame",
            ),
            timebase=789,
            point_num=1,
            lidar_id=2,
            rsvd=np.asarray([0, 1, 2], dtype=np.uint8),
            points=[
                SimpleNamespace(
                    offset_time=42,
                    x=1.0,
                    y=2.0,
                    z=3.0,
                    reflectivity=4,
                    tag=5,
                    line=6,
                )
            ],
        )

        converted = _convert_livox_custom_message(source, typestore)
        cdr = typestore.serialize_cdr(converted, LIVOX2_CUSTOM_MSG_TYPE)
        restored = typestore.deserialize_cdr(cdr, LIVOX2_CUSTOM_MSG_TYPE)

        self.assertEqual(restored.__msgtype__, LIVOX2_CUSTOM_MSG_TYPE)
        self.assertEqual(restored.header.frame_id, "livox_frame")
        self.assertEqual(restored.timebase, 789)
        self.assertEqual(restored.point_num, 1)
        self.assertEqual(restored.points[0].offset_time, 42)
        self.assertEqual(restored.points[0].line, 6)
