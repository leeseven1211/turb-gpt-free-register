from contextlib import contextmanager
from types import SimpleNamespace

from core.runtime.assembly import _HeartbeatBinding
from core.runtime.context import RuntimeContext
from core.runtime.instance_owner import OwnerError, OwnerIdentity
from core.runtime import worker_heartbeat
from core.storage import postgres, runtime_workers


def test_heartbeat_waiting_for_pool_cannot_publish_preresume_readiness(monkeypatch):
    owner = SimpleNamespace(paused=False)
    owner.status = lambda: SimpleNamespace(identity=OwnerIdentity('host', 1, 'start', 'nonce'))

    def require_owner():
        if owner.paused:
            raise OwnerError('owner_probe_paused')

    owner.require_owner = require_owner
    context = RuntimeContext('worker')
    bootstrap = SimpleNamespace(release='test', instance_id='test')
    binding = _HeartbeatBinding(context, owner, bootstrap, lambda: {'ready': True})
    borrower = SimpleNamespace(count=0)
    connection = object()
    history = []

    @contextmanager
    def connect():
        borrower.count += 1
        if borrower.count == 2:
            owner.paused = True
            binding.owner_pause_changed()
            owner.paused = False
            binding.owner_pause_changed()
        yield connection

    class Reporter:
        def __init__(self, *, admission, write_heartbeat, collect_status):
            self.collect = collect_status
            self.write = write_heartbeat
            self.wakes = 0

        def start(self):
            pass

        def request_refresh(self):
            self.wakes += 1

    def heartbeat(generation, status, *, conn=None):
        # Mirror lazy pool checkout when the caller did not supply a connection.
        if conn is None:
            with postgres.connect() as current:
                return heartbeat(generation, status, conn=current)
        assert conn is connection
        history.append((generation, status['ready']))
        return True

    monkeypatch.setattr(postgres, 'connect', connect)
    monkeypatch.setattr(runtime_workers, 'ensure_tables', lambda conn: None)
    monkeypatch.setattr(runtime_workers, 'begin_generation', lambda *a, **kw: 'generation')
    monkeypatch.setattr(runtime_workers, 'heartbeat', heartbeat)
    monkeypatch.setattr(worker_heartbeat, 'WorkerHeartbeat', Reporter)
    binding.start()
    reporter = binding.reporter
    assert reporter.write(reporter.collect())
    assert reporter.write(reporter.collect())
    assert history == [('generation', False), ('generation', True)]
    assert reporter.wakes == 2
