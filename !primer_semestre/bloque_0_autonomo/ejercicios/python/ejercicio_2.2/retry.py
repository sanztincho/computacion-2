import functools
import time
import traceback
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    """Decorador que reintenta la función si lanza excepciones.

    Parámetros:
    - max_attempts: int - número máximo de intentos (por defecto 3)
    - delay: float - segundos a esperar entre intentos (por defecto 1.0)
    - exceptions: tupla de tipos de excepción (por defecto (Exception,))

    Si todos los intentos fallan, se re-lanza la última excepción.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts debe ser al menos 1")
    if delay < 0:
        raise ValueError("delay no puede ser negativo")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[BaseException] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        print(f"Intento {attempt}/{max_attempts} exitoso")
                    return result
                except exceptions as exc:
                    last_exception = exc
                    is_last = attempt == max_attempts
                    if is_last:
                        print(
                            f"Intento {attempt}/{max_attempts} falló: {exc}. "
                            f"No quedan reintentos."
                        )
                    else:
                        print(
                            f"Intento {attempt}/{max_attempts} falló: {exc}. "
                            f"Esperando {delay}s..."
                        )
                        time.sleep(delay)
                    # Continúa al siguiente intento o sale con raise en el último
            assert last_exception is not None
            raise last_exception

        # Exponer algunas utilidades adicionales si se necesita
        wrapper.retry_config = {
            "max_attempts": max_attempts,
            "delay": delay,
            "exceptions": exceptions,
        }
        return wrapper  # type: ignore[return-value]

    return decorator


if __name__ == "__main__":
    import random

    @retry(max_attempts=3, delay=0.5)
    def conectar_servidor() -> str:
        """Simula conexión con 70% chance de fallo."""
        if random.random() < 0.7:
            raise ConnectionError("Servidor no disponible")
        return "Conectado exitosamente"

    print("Ejecutando prueba de retry...")
    try:
        print(conectar_servidor())
    except ConnectionError as exc:
        print(f"Falló después de 3 intentos: {exc}")

    # Prueba determinista usando una función que falla siempre
    @retry(max_attempts=2, delay=0.1, exceptions=(ValueError,))
    def lambda_fallida() -> str:
        raise ValueError("error de prueba")

    try:
        lambda_fallida()
    except ValueError as exc:
        print(f"Se capturó ValueError final: {exc}")
