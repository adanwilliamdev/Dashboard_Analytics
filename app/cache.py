"""Cache de resultados por usuario: memoria (padrao) ou Redis (REDIS_URL).

Invalidacao por "versao" do namespace: ao gravar dados do usuario, `invalidate()` incrementa
a versao e todas as chaves antigas deixam de ser lidas (expiram sozinhas pelo TTL).
Falhas do Redis nunca derrubam a API: o cache simplesmente e ignorado.
"""
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("dashboard.cache")
_MAX_MEMORY_KEYS = 5000


class MemoryBackend:
    def __init__(self):
        self._data: Dict[str, Tuple[float, str]] = {}
        self._versions: Dict[str, int] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry[0] < time.monotonic():
                del self._data[key]
                return None
            return entry[1]

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            if len(self._data) >= _MAX_MEMORY_KEYS:
                now = time.monotonic()
                self._data = {k: v for k, v in self._data.items() if v[0] >= now}
                if len(self._data) >= _MAX_MEMORY_KEYS:
                    self._data.clear()
            self._data[key] = (time.monotonic() + ttl, value)

    def version(self, namespace: str) -> int:
        with self._lock:
            return self._versions.get(namespace, 0)

    def bump(self, namespace: str) -> None:
        with self._lock:
            self._versions[namespace] = self._versions.get(namespace, 0) + 1

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._versions.clear()


class RedisBackend:  # pragma: no cover - exige um Redis real
    def __init__(self, url: str):
        import redis

        self._r = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)

    def get(self, key: str) -> Optional[str]:
        raw = self._r.get("cache:" + key)
        return raw.decode() if raw is not None else None

    def set(self, key: str, value: str, ttl: int) -> None:
        self._r.setex("cache:" + key, ttl, value)

    def version(self, namespace: str) -> int:
        return int(self._r.get("cachever:" + namespace) or 0)

    def bump(self, namespace: str) -> None:
        self._r.incr("cachever:" + namespace)

    def clear(self) -> None:
        for k in self._r.scan_iter("cache*"):
            self._r.delete(k)


class Cache:
    def __init__(self, backend=None, ttl: int = 30):
        self.backend = backend or MemoryBackend()
        self.ttl = ttl

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def get_or_set(self, namespace: str, key: str, loader: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        if not self.enabled:
            return loader()
        try:
            full = f"{namespace}:{self.backend.version(namespace)}:{key}"
            hit = self.backend.get(full)
            if hit is not None:
                return json.loads(hit)
        except Exception as exc:  # cache nunca derruba a API
            logger.warning("cache indisponivel (leitura): %s", exc)
            return loader()
        value = loader()
        try:
            self.backend.set(full, json.dumps(value, allow_nan=False), ttl or self.ttl)
        except Exception as exc:
            logger.warning("cache indisponivel (escrita): %s", exc)
        return value

    def invalidate(self, namespace: str) -> None:
        try:
            self.backend.bump(namespace)
        except Exception as exc:
            logger.warning("cache indisponivel (invalidacao): %s", exc)

    def clear(self) -> None:
        try:
            self.backend.clear()
        except Exception as exc:
            logger.warning("cache indisponivel (clear): %s", exc)


def _worker_count() -> int:
    """Numero de processos da API (variavel padrao WEB_CONCURRENCY, lida tambem pelo uvicorn)."""
    try:
        return max(int(os.getenv("WEB_CONCURRENCY", "1")), 1)
    except ValueError:
        return 1


def build_cache() -> Cache:
    from app.config import settings  # import tardio: o modulo continua testavel sem a stack web

    if settings.REDIS_URL:
        try:
            return Cache(RedisBackend(settings.REDIS_URL), settings.CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("Redis indisponivel (%s); usando cache em memoria", exc)
    workers = _worker_count()
    if workers > 1 and settings.CACHE_TTL_SECONDS > 0:
        # Cada worker teria o proprio cache e a invalidacao so valeria no que gravou: o usuario
        # veria dado velho por ate CACHE_TTL_SECONDS. Sem Redis, e mais seguro nao cachear.
        logger.warning(
            "WEB_CONCURRENCY=%s sem REDIS_URL: cache desativado (memoria nao e compartilhada entre "
            "workers). Defina REDIS_URL para habilitar o cache.", workers,
        )
        return Cache(MemoryBackend(), 0)
    return Cache(MemoryBackend(), settings.CACHE_TTL_SECONDS)


_cache: Optional[Cache] = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = build_cache()
    return _cache


def user_ns(user_id: int) -> str:
    return f"user:{user_id}"
