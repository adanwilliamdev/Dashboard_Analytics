from app.cache import Cache, MemoryBackend


def test_caches_and_returns_independent_copies():
    c, calls = Cache(MemoryBackend(), ttl=30), []

    def loader():
        calls.append(1)
        return {"x": [1, 2]}

    a = c.get_or_set("user:1", "k", loader)
    a["x"].append(99)  # mutar o retorno nao pode contaminar o cache
    b = c.get_or_set("user:1", "k", loader)
    assert len(calls) == 1 and b == {"x": [1, 2]}


def test_invalidate_only_affects_that_namespace():
    c = Cache(MemoryBackend(), ttl=30)
    n = {"a": 0, "b": 0}

    def load(name):
        def f():
            n[name] += 1
            return n[name]
        return f

    c.get_or_set("user:1", "k", load("a"))
    c.get_or_set("user:2", "k", load("b"))
    c.invalidate("user:1")
    assert c.get_or_set("user:1", "k", load("a")) == 2  # recarregou
    assert c.get_or_set("user:2", "k", load("b")) == 1  # intacto


def test_ttl_zero_disables_cache():
    c, calls = Cache(MemoryBackend(), ttl=0), []
    c.get_or_set("u", "k", lambda: calls.append(1) or 1)
    c.get_or_set("u", "k", lambda: calls.append(1) or 1)
    assert len(calls) == 2


def test_expiry():
    import time

    c, calls = Cache(MemoryBackend(), ttl=30), []
    c.get_or_set("u", "k", lambda: calls.append(1) or 1, ttl=1)
    time.sleep(1.1)
    c.get_or_set("u", "k", lambda: calls.append(1) or 1, ttl=1)
    assert len(calls) == 2


def test_backend_failure_never_breaks_loader():
    class Broken(MemoryBackend):
        def get(self, key):
            raise RuntimeError("redis caiu")

    c = Cache(Broken(), ttl=30)
    assert c.get_or_set("u", "k", lambda: 42) == 42
    c.invalidate("u")  # nao levanta excecao
