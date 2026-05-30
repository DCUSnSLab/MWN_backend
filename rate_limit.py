"""rate_limit: Flask-Limiter 싱글톤.

단일 워커(gunicorn --workers 1) 환경에서 memory 스토리지로 충분하다.
멀티 워커/멀티 레플리카로 확장 시 storage_uri 를 Redis 등으로 교체해야 한다.
키는 ProxyFix 가 복원한 X-Forwarded-For 의 client IP 를 사용한다.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
    headers_enabled=True,
)
