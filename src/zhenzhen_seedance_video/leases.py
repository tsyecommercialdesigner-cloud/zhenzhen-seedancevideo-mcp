"""Monotonic Host leases and irreversible draining, independent of task facts."""

import time


class LeaseManager:
    def __init__(self, *, lease_seconds, grace_seconds, drain_seconds, clock=time.monotonic):
        self.clock = clock
        self.lease_seconds = lease_seconds
        self.grace_seconds = grace_seconds
        self.drain_seconds = drain_seconds
        self.hosts = {}
        self.empty_since = clock()
        self.draining_since = None
        self._expired = []

    def join(self, host):
        self.tick(collect=False)
        if self.draining_since is not None:
            return False
        self.hosts[host] = self.clock() + self.lease_seconds
        self.empty_since = None
        return True

    def touch(self, host):
        if host not in self.hosts or self.clock() >= self.hosts[host]:
            self.drop(host)
            return False
        self.hosts[host] = self.clock() + self.lease_seconds
        return True

    def drop(self, host):
        self.hosts.pop(host, None)
        if not self.hosts and self.empty_since is None:
            self.empty_since = self.clock()

    def tick(self, *, collect=True):
        now = self.clock()
        expired = [host for host, deadline in self.hosts.items() if deadline <= now]
        for host in expired:
            self.drop(host)
        self._expired.extend(expired)
        if self.empty_since is not None and now >= self.empty_since + self.grace_seconds:
            if self.draining_since is None:
                self.draining_since = self.empty_since + self.grace_seconds
        if collect:
            expired, self._expired = self._expired, []
            return expired
        return []

    @property
    def dispatch_allowed(self):
        self.tick(collect=False)
        return bool(self.hosts) and self.draining_since is None

    @property
    def network_allowed(self):
        self.tick(collect=False)
        return self.draining_since is None

    @property
    def drain_expired(self):
        self.tick(collect=False)
        return (
            self.draining_since is not None
            and self.clock() >= self.draining_since + self.drain_seconds
        )
