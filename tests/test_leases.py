from zhenzhen_seedance_video.leases import LeaseManager


def manager(clock):
    return LeaseManager(
        lease_seconds=20, grace_seconds=10, drain_seconds=15, clock=lambda: clock.monotonic
    )


def test_a_exits_b_keeps_backend_alive(clock):
    leases = manager(clock)
    assert leases.join("a") and leases.join("b")
    leases.drop("a")
    assert leases.dispatch_allowed
    leases.drop("b")
    assert not leases.dispatch_allowed
    assert leases.network_allowed
    clock.advance(9)
    assert leases.join("c")
    assert leases.dispatch_allowed


def test_expiry_and_irreversible_finite_drain(clock):
    leases = manager(clock)
    leases.join("a")
    clock.advance(20)
    assert leases.tick() == ["a"]
    assert not leases.touch("a")
    assert not leases.dispatch_allowed
    clock.advance(10)
    assert not leases.network_allowed
    assert not leases.join("b")
    assert not leases.drain_expired
    clock.advance(15)
    assert leases.drain_expired


def test_heartbeat_extends_only_live_lease(clock):
    leases = manager(clock)
    leases.join("a")
    clock.advance(19)
    assert leases.touch("a")
    clock.advance(2)
    assert leases.tick() == []


def test_reading_gate_does_not_lose_expired_connection_cleanup(clock):
    leases = manager(clock)
    leases.join("old")
    clock.advance(20)
    assert not leases.dispatch_allowed
    assert leases.join("new")
    assert leases.tick() == ["old"]
