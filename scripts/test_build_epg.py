import gzip
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from build_epg import build


class EpgTests(unittest.TestCase):
    def test_maps_ids_and_drops_unrelated_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.xml"
            output = Path(folder) / "epg.xml.gz"
            channels = "".join(
                f'<channel id="source-{index}"><display-name>C {index}</display-name></channel>'
                for index in range(8)
            )
            programmes = "".join(
                f'<programme channel="source-{index % 8}" start="20260907000000 +0000" stop="20260907010000 +0000"><title>P {index}</title></programme>'
                for index in range(40)
            )
            source.write_text(f"<?xml version='1.0'?><tv>{channels}{programmes}<channel id='other'/></tv>")
            mapping = {f"source-{index}": f"target-{index}" for index in range(8)}
            with patch("build_epg.SOURCE_TO_TARGET", mapping):
                self.assertEqual(build(str(source), output), (8, 40))
            root = ET.fromstring(gzip.decompress(output.read_bytes()))
            self.assertEqual({node.get("id") for node in root.findall("channel")}, set(mapping.values()))
            self.assertEqual(len(root.findall("programme")), 40)


if __name__ == "__main__":
    unittest.main()
