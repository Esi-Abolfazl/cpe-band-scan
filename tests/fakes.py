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
