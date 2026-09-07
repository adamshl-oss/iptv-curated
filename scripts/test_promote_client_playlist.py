import copy
import hashlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import promote_client_playlist as promotion
from audit_client_playlist import assess


def manifest(*ids):
    return '#EXTM3U\n' + ''.join(
        f'#EXTINF:-1 tvg-id="{key}",{key}\nhttps://example.test/{key}.m3u8\n'
        for key in ids)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.candidate = root / 'candidate.m3u'
        self.client = root / 'client.m3u'
        self.alias = root / 'alias.m3u'
        self.policy = root / 'policy.json'
        self.candidate.write_text(manifest('old', 'new'))
        self.client.write_text(manifest('old', 'omitted'))
        self.alias.write_bytes(self.client.read_bytes())
        self.policy.write_text('{}')
        for key, value in dict(CANDIDATE=self.candidate,
                               CLIENT_ALIASES=(self.alias, self.client),
                               HEALTH_POLICY_PATH=self.policy).items():
            patcher = patch.object(promotion, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.report = dict(
            checked_at=datetime.now(timezone.utc).isoformat(), apple_required=True,
            policy_sha256=hashlib.sha256(self.policy.read_bytes()).hexdigest(),
            source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (self.client, self.candidate)},
            results=[dict(tvg_id=key, url=f'https://example.test/{key}.m3u8',
                          passed=True, quality_passed=True, successes=3,
                          apple_passed=True, sustained_passed=True,
                          details=['1:h264/aac 1280x720, moving',
                                   '2:h264/aac 1280x720, moving',
                                   '3:h264/aac 1280x720, moving'])
                     for key in ('old', 'new', 'omitted')])

    def test_preserves_healthy_omitted_channel(self):
        self.assertEqual(len(promotion.verified_entries(self.report)), 3)

    def test_removes_only_three_startup_failures(self):
        self.report['results'][2].update(passed=False, successes=0)
        with patch.object(promotion, 'durably_quarantined', return_value=True):
            self.assertEqual(len(promotion.verified_entries(self.report)), 2)

    def test_three_startup_failures_alone_cannot_remove(self):
        self.report['results'][2].update(passed=False, successes=0)
        with patch.object(promotion, 'durably_quarantined', return_value=False):
            self.assertEqual(len(promotion.verified_entries(self.report)), 3)

    def test_one_transient_failure_cannot_remove(self):
        self.report['results'][2].update(passed=False, successes=2)
        self.assertEqual(len(promotion.verified_entries(self.report)), 3)
        self.assertEqual(self.report['promotion_decisions']['degraded_retained'], ['omitted'])

    def test_audit_exception_cannot_remove(self):
        self.report['results'][2].update(passed=False, successes=0, audit_error=True)
        self.assertEqual(len(promotion.verified_entries(self.report)), 3)

    def test_no_new_low_quality_channel(self):
        self.report['results'][1]['details'] = [f'{i}:h264/aac 512x288, moving' for i in range(1,4)]
        self.assertEqual(len(promotion.verified_entries(self.report)), 2)
        self.assertEqual(self.report['promotion_decisions']['unproven_skipped'], ['new'])

    def test_existing_low_quality_is_not_silently_removed(self):
        self.report['results'][0]['details'] = [f'{i}:h264/aac 512x288, moving' for i in range(1,4)]
        self.assertEqual(len(promotion.verified_entries(self.report)), 3)

    def test_changed_manifest_rejects_evidence(self):
        self.candidate.write_text(manifest('different'))
        with self.assertRaises(ValueError):
            promotion.verified_entries(self.report)

    def test_inconsistent_gate_cannot_add(self):
        self.report['results'][1].update(passed=True, successes=0, apple_passed=False)
        self.assertEqual(len(promotion.verified_entries(self.report)), 2)

    def test_one_bad_candidate_does_not_block_other_improvements(self):
        self.report['results'][0].update(passed=False, successes=2)
        self.assertEqual(len(promotion.verified_entries(self.report)), 3)
        self.assertEqual(self.report['promotion_decisions']['degraded_retained'], ['old'])

    def test_health_tracks_same_channel_different_urls_independently(self):
        import json
        report = copy.deepcopy(self.report)
        replacement = copy.deepcopy(report['results'][0])
        replacement.update(url='https://example.test/replacement.m3u8', passed=False, successes=0)
        report['results'].append(replacement)
        with patch.object(promotion, 'ROOT', Path(self.temp.name)):
            promotion.record_health(report)
            promotion.record_health(report)  # Same evidence cannot count twice.
        saved = json.loads((Path(self.temp.name) / 'releases/client-health.json').read_text())
        sources = saved['channels']['old']['sources']
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources['https://example.test/old.m3u8']['failure_streak'], 0)
        self.assertEqual(sources['https://example.test/replacement.m3u8']['failure_streak'], 1)

    def test_wrong_url_rejects_evidence(self):
        self.report['results'][1]['url'] = 'https://example.test/other.m3u8'
        self.assertEqual(len(promotion.verified_entries(self.report)), 2)

    def test_stale_or_missing_apple_or_changed_policy_rejected(self):
        for change in (
            {'checked_at': (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()},
            {'apple_required': False}, {'policy_sha256': 'wrong'},
        ):
            report = copy.deepcopy(self.report)
            report.update(change)
            with self.assertRaises(ValueError):
                promotion.verified_entries(report)

    def test_frozen_video_not_excused_by_apple_timeline(self):
        result = dict(passed=True, sustained_passed=False, details=[
            '1:h264/aac 1280x720, moving', '2:h264/aac 1280x720, moving',
            '3:h264/aac 1280x720, moving',
            'sustained:long_freeze_20.0s; media=60.0s; wall=64.0s; lag=4.0s; freezes=1/20.0s/max20.0s; errors=0'])
        self.assertFalse(assess(result)['passed'])

    def test_only_pacing_can_be_resolved_by_apple_playback(self):
        result = dict(passed=True, sustained_passed=False, details=[
            '1:h264/aac 512x288, moving', '2:h264/aac 512x288, moving',
            '3:h264/aac 512x288, moving',
            'sustained:buffering_25.0s; media=60.0s; wall=85.0s; lag=25.0s; freezes=0/0.0s/max0.0s; errors=0'])
        checked = assess(result)
        self.assertTrue(checked['passed'])
        self.assertFalse(checked['quality_passed'])
        self.assertEqual(checked['height'], 288)


if __name__ == '__main__':
    unittest.main()
