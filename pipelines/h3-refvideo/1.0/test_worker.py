"""Graph contract tests; no Modal lookup or GPU invocation."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).with_name('worker.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ReferenceVideoTests(unittest.TestCase):
    def build(self, image=''):
        return worker.build_reference_video('Follow <Video 1> motion and camera.', 'guide/test.mp4', image)

    def test_both_conditioning_stages_receive_video(self):
        api, meta = self.build()
        for key in ('313', '315'):
            self.assertEqual(api[key]['inputs']['ref_videos.ref_video_0'], ['refvideo_loader_v1', 0])
            self.assertNotIn('ref_images', api[key]['inputs'])
        self.assertFalse(any(n['class_type'] == 'DenoMiniMaxH3ReferenceImageLoader' for n in api.values()))
        self.assertEqual(meta['generated_frames'], 107)
        self.assertEqual(api['refvideo_loader_v1']['inputs']['force_rate'], 24)

    def test_image_and_video_are_separate(self):
        api, _ = self.build('look.png')
        self.assertEqual(api['314']['inputs']['image_paths'], 'look.png')
        self.assertEqual(api['313']['inputs']['ref_images'], ['314', 0])
        self.assertEqual(api['refvideo_loader_v1']['inputs']['video'], '/data/input/guide/test.mp4')

    def test_all_links_resolve(self):
        api, _ = self.build('look.png')
        for node in api.values():
            for val in node['inputs'].values():
                if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                    self.assertIn(val[0], api)

    def test_unsafe_paths_rejected(self):
        for path in ('../secret', '/tmp/file', 'C:/file', 'a/../../b', '', 'a\nb'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                worker.safe_input(path)

    def test_bad_inputs_fail_before_submission(self):
        for kwargs in ({'reference_video': 'a.png'}, {'seconds': float('nan')},
                       {'seconds': 0}, {'width': 721}, {'prompt': 'no reference tag'}):
            values = {'prompt': 'Use <Video 1>', 'reference_video': 'a.mp4', **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                worker.build_reference_video(**values)


if __name__ == '__main__':
    unittest.main()
