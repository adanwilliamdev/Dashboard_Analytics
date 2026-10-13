"""Protecao contra forca bruta no login.

Com ``REDIS_URL`` o contador e compartilhado entre workers/instancias (janela fixa: a primeira
falha abre a janela e ela expira sozinha). Sem Redis, o contador vive na memoria do processo.
Se o Redis cair, o login NAO fica sem protecao: cai no contador em memoria (por processo).

Atras de proxy reverso, ``request.client.host`` so reflete o IP real se o uvicorn confiar no proxy:
defina ``FORWARDED_ALLOW_IPS`` com o IP/CIDR do proxy (veja o README).
"""
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger("dashboard.security")


def _too_many_attempts(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Muitas tentativas de login. Tente novamente em instantes.",
        headers={"Retry-After": str(max(int(retry_after), 1))},
    )


class LoginRateLimiter:
    """Contador em memoria (janela deslizante), por processo."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._fails: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        q = self._fails[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) >= self.max_attempts:
                raise _too_many_attempts(self.window - (now - q[0]))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._fails[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._fails.clear()


class RedisLoginRateLimiter:
    """Contador compartilhado no Redis (janela fixa). Mesma interface do limitador em memoria."""

    PREFIX = "loginfail:"

    def __init__(self, max_attempts: int, window_seconds: int, url: str = "", client=None):
        self.max_attempts = max_attempts
        self.window = window_seconds
        if client is None:  # pragma: no cover - exige um Redis real
            import redis

            client = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
        self._r = client
        self._fallback = LoginRateLimiter(max_attempts, window_seconds)

    def _warn(self, action: str, exc: Exception) -> None:
        logger.warning("rate limit: Redis indisponivel (%s): %s; usando contador local", action, exc)

    def check(self, key: str) -> None:
        try:
            raw = self._r.get(self.PREFIX + key)
            if raw is not None and int(raw) >= self.max_attempts:
                ttl = int(self._r.ttl(self.PREFIX + key))
                raise _too_many_attempts(ttl if ttl > 0 else self.window)
        except HTTPException:
            raise
        except Exception as exc:
            self._warn("check", exc)
        self._fallback.check(key)  # sem custo quando o Redis responde: so conta falhas locais do fallback

    def record_failure(self, key: str) -> None:
        try:
            k = self.PREFIX + key
            count = int(self._r.incr(k))
            if count == 1 or int(self._r.ttl(k)) < 0:  # garante TTL mesmo se um expire anterior falhou
                self._r.expire(k, self.window)
        except Exception as exc:
            self._warn("record_failure", exc)
            self._fallback.record_failure(key)

    def reset(self, key: str) -> None:
        self._fallback.reset(key)
        try:
            self._r.delete(self.PREFIX + key)
        except Exception as exc:
            self._warn("reset", exc)

    def reset_all(self) -> None:
        self._fallback.reset_all()
        try:
            for k in self._r.scan_iter(self.PREFIX + "*"):
                self._r.delete(k)
        except Exception as exc:
            self._warn("reset_all", exc)


def build_login_limiter(redis_url: Optional[str] = None):
    url = settings.REDIS_URL if redis_url is None else redis_url
    if url:
        try:
            return RedisLoginRateLimiter(settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS, url=url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis indisponivel (%s); rate limit de login em memoria", exc)
    return LoginRateLimiter(settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS)


login_limiter = build_login_limiter()
