import unittest

from cyber_lion.architecture_projection.layout import DISPLAY_PLANES, PLANE_LAYER_BINDINGS, canonical_layout


class ArchitectureProjectionLayoutTests(unittest.TestCase):
    def test_layout_is_deterministic_and_covers_display_planes(self):
        first = canonical_layout()
        second = canonical_layout()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 9)
        self.assertEqual(tuple(item.plane for item in first), DISPLAY_PLANES)
        self.assertEqual(tuple(item.rank for item in first), tuple(range(9)))

    def test_status_is_not_encoded_by_layout_or_color(self):
        for item in canonical_layout():
            self.assertEqual(item.layers, PLANE_LAYER_BINDINGS[item.plane])
            self.assertFalse(hasattr(item, "color"))
            self.assertFalse(hasattr(item, "status"))


if __name__ == "__main__":
    unittest.main()
