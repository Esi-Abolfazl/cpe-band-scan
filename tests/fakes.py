"""A stand-in for huawei_lte_api's Connection. Tests never touch a real router."""


class FakeSession:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, endpoint, prefix=None):
        key = f"config/{endpoint}" if prefix == "config" else endpoint
        value = self.data[key]
        if isinstance(value, Seq):
            value = value.next()
        if isinstance(value, Exception):
            raise value
        return value

    def post_set(self, endpoint, data):
        value = self.data.get(f"POST {endpoint}")
        if isinstance(value, Exception):
            raise value
        self.posts.append((endpoint, data))
        return "OK"


def factory(session=None, connect_error=None):
    """Build a connection_factory for Router. `connect_error` fires at login time."""

    def make(url, username=None, password=None):
        if connect_error is not None:
            raise connect_error
        return session if session is not None else FakeSession()

    return make


class Seq:
    """A value that advances on each read, for sampling tests. The last value repeats."""

    def __init__(self, values):
        self.values = list(values)

    def next(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class FakeProbe:
    """Stands in for speed.SpeedProbe: no sockets, a fixed verdict, one reading per band."""

    READING = {"latency_ms": 80, "jitter_ms": 10, "mbps": 25.0, "bytes": 15_000_000, "seconds": 5.0}

    def __init__(self, router_url="", bypass="confirmed", readings=None):
        self.router_url = router_url
        self.bypass = bypass
        self.readings = list(readings or [])
        self.started = 0
        self.measured = 0

    def start(self):
        self.started += 1
        return {"bypass": self.bypass, "lan_ip": "192.168.8.2", "public_ip": "5.1.1.1"}

    def measure(self):
        self.measured += 1
        return self.readings.pop(0) if self.readings else dict(self.READING)
