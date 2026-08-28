import datetime
import os
import tempfile
import unittest
from unittest import mock

from mod_ci.controllers import ARTIFACT_SWEEP_STAMP, prune_test_artifacts


def _blob(name, age_days):
    """A stand-in bucket blob created age_days ago."""
    blob = mock.MagicMock()
    blob.name = name
    now = datetime.datetime.now(datetime.timezone.utc)
    blob.time_created = now - datetime.timedelta(days=age_days)
    return blob


class TestArtifactRetention(unittest.TestCase):
    """Age-out of run artifacts, which nothing removed before."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.log = mock.MagicMock()

    def _run(self, blobs, days=90):
        bucket = mock.MagicMock()
        bucket.list_blobs.return_value = blobs
        with mock.patch('run.storage_client_bucket', bucket):
            return prune_test_artifacts(self.log, self.repo, days)

    def test_only_blobs_past_the_window_are_deleted(self):
        old, fresh = _blob('test_artifacts/1/ccextractor', 200), _blob('test_artifacts/2/coredump', 3)
        self.assertEqual(self._run([old, fresh]), 1)
        old.delete.assert_called_once()
        fresh.delete.assert_not_called()

    def test_zero_days_disables_retention(self):
        old = _blob('test_artifacts/1/ccextractor', 999)
        self.assertEqual(self._run([old], days=0), 0)
        old.delete.assert_not_called()

    def test_second_sweep_within_a_day_does_nothing(self):
        self.assertEqual(self._run([_blob('test_artifacts/1/ccextractor', 200)]), 1)
        # The cron fires every ten minutes; only the first sweep should work.
        self.assertEqual(self._run([_blob('test_artifacts/1/ccextractor', 200)]), 0)

    def test_a_denied_delete_stops_the_sweep(self):
        # A service account without storage.objects.delete fails identically
        # on every blob, so the sweep must not grind through all of them.
        first, second = _blob('test_artifacts/1/a', 200), _blob('test_artifacts/2/b', 200)
        first.delete.side_effect = Exception('403 Forbidden')
        self.assertEqual(self._run([first, second]), 0)
        second.delete.assert_not_called()
        self.log.warning.assert_called_once()

    def test_stale_local_directories_are_removed(self):
        root = os.path.join(self.repo, 'test_artifacts')
        old_dir, new_dir = os.path.join(root, '1'), os.path.join(root, '2')
        os.makedirs(old_dir)
        os.makedirs(new_dir)
        now = datetime.datetime.now(datetime.timezone.utc)
        stale = (now - datetime.timedelta(days=200)).timestamp()
        os.utime(old_dir, (stale, stale))

        self._run([])

        self.assertFalse(os.path.isdir(old_dir))
        self.assertTrue(os.path.isdir(new_dir))

    def test_sweep_runs_without_a_bucket_configured(self):
        with mock.patch('run.storage_client_bucket', None):
            self.assertEqual(prune_test_artifacts(self.log, self.repo, 90), 0)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, ARTIFACT_SWEEP_STAMP)))
