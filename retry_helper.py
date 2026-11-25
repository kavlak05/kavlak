import random
import time
from safe_evaluator import logger


def _is_503_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "503" in message or "high demand" in message or "unavailable" in message


def run_with_503_retry(fn, *args, max_retries: int = 3, base_delay: float = 1.0, **kwargs):
    """503 gecici hatalarinda ustel geri cekilme (exponential backoff) ile yeniden dener."""
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_503_error(exc) or attempt == max_retries:
                logger.error("Çağrı başarısız (deneme %s/%s): %s", attempt + 1, max_retries + 1, exc)
                raise
            sleep_time = base_delay * (2 ** attempt) + random.uniform(0.0, 0.3)
            logger.warning(
                "503 algılandı, %.2f sn sonra yeniden denenecek (deneme %s/%s)",
                sleep_time,
                attempt + 1,
                max_retries,
            )
            time.sleep(sleep_time)
