"""Exercise file-lock cleanup and inode rules using fake POSIX syscalls."""
import importlib.util
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('candidate_file_owner',Path(__file__).resolve().parents[2] / 'core/runtime/instance_owner.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)

class FileLeaseTests(unittest.TestCase):
    def setUp(self):
        self.path=Path('/stable/execution-owner/safe.lock')
        self.lease=module.PosixFileLease(self.path)
        self.mkdir=self.start(patch.object(Path,'mkdir'))
        self.open=self.start(patch.object(module.os,'open',return_value=47))
        self.stat=self.start(patch.object(module.os,'fstat',return_value=SimpleNamespace(st_mode=stat.S_IFREG,st_uid=1000,st_nlink=1)))
        self.start(patch.object(module.os,'geteuid',return_value=1000))
        self.close=self.start(patch.object(module.os,'close'))
        self.flock=self.start(patch('fcntl.flock'))
    def start(self,p):value=p.start();self.addCleanup(p.stop);return value
    def test_acquisition_is_nonblocking_nofollow_closeonexec_and_mode_private(self):
        import fcntl
        self.lease.acquire();self.assertTrue(self.lease.held)
        args=self.open.call_args.args;self.assertEqual(args[0],self.path);self.assertEqual(args[2],0o600)
        self.assertTrue(args[1]&module.os.O_NOFOLLOW);self.assertTrue(args[1]&module.os.O_CLOEXEC)
        self.flock.assert_called_once_with(47,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_busy_file_closes_only_new_descriptor_without_unlink(self):
        self.flock.side_effect=BlockingIOError()
        with self.assertRaisesRegex(module.OwnerError,'owner_file_busy'):self.lease.acquire()
        self.assertFalse(self.lease.held);self.close.assert_called_once_with(47)
    def test_wrong_owner_nonregular_or_hardlinked_file_never_takes_lock(self):
        for info in [SimpleNamespace(st_mode=stat.S_IFREG,st_uid=5,st_nlink=1),SimpleNamespace(st_mode=stat.S_IFDIR,st_uid=1000,st_nlink=1),SimpleNamespace(st_mode=stat.S_IFREG,st_uid=1000,st_nlink=2)]:
            with self.subTest(info=info):
                self.stat.return_value=info
                with self.assertRaisesRegex(module.OwnerError,'owner_file_invalid'):self.lease.acquire()
        self.flock.assert_not_called();self.assertEqual(self.close.call_count,3)
    def test_close_is_idempotent_no_unlock_or_unlink_and_cannot_touch_reused_fd(self):
        self.lease.acquire();self.lease.close();self.lease.close()
        self.assertFalse(self.lease.held);self.close.assert_called_once_with(47)
        self.assertEqual(self.flock.call_count,1)
    def test_uncertain_os_close_never_retries_a_possibly_reused_descriptor(self):
        self.lease.acquire();self.close.side_effect=OSError('interrupted close')
        with self.assertRaises(OSError):self.lease.close()
        self.close.side_effect=None
        with self.assertRaisesRegex(module.OwnerError,'owner_file_close_unknown'):self.lease.close()
        self.close.assert_called_once_with(47)
    def test_metadata_uses_held_descriptor_and_handles_partial_writes(self):
        self.lease.acquire();chunks=[]
        def write(fd,data):self.assertEqual(fd,47);chunks.append(data[:2]);return min(2,len(data))
        with patch.object(module.os,'write',side_effect=write),patch.object(module.os,'lseek') as seek,patch.object(module.os,'ftruncate') as truncate:
            self.lease.write_metadata({'state':'held'})
        data=b''.join(chunks);self.assertEqual(data,b'{"state":"held"}\n');seek.assert_called_once_with(47,0,module.os.SEEK_SET);truncate.assert_called_once_with(47,len(data))
    def test_unheld_file_cannot_write_metadata(self):
        with self.assertRaisesRegex(module.OwnerError,'owner_file_not_held'):self.lease.write_metadata({})

if __name__=='__main__':unittest.main(verbosity=2)
