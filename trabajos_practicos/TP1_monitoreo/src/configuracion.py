"""
configuracion.py
================

Carga config.json (intervalos por vista, filtros y orden por defecto) con
un merge sobre valores por defecto embebidos en el codigo, para que el
monitor pueda arrancar incluso si config.json no existe o esta incompleto.
"""

import json
import os

CONFIG_POR_DEFECTO = {
    "intervalos": {
        "resumen":    {"default": 2.0,  "min": 0.5},
        "memoria":    {"default": 3.0,  "min": 1.0},
        "fds":        {"default": 5.0,  "min": 2.0},
        "threads":    {"default": 2.0,  "min": 0.5},
        "senales":    {"default": 10.0, "min": 5.0},
        "scheduling": {"default": 10.0, "min": 5.0},
        "sistema":    {"default": 2.0,  "min": 1.0},
    },
    "filtro_default": "",
    "usuario_default": "",
    "orden_default": "cpu",
    "verbose_default": False,
}


def _copia_profunda(d):
    return json.loads(json.dumps(d))


def _fusionar(base, extra):
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _fusionar(base[clave], valor)
        else:
            base[clave] = valor


def cargar_config(ruta):
    config = _copia_profunda(CONFIG_POR_DEFECTO)
    if ruta and os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                disco = json.load(f)
            _fusionar(config, disco)
        except (json.JSONDecodeError, OSError):
            # Config invalido: seguimos con los valores por defecto en vez
            # de crashear el monitor.
            pass
    return config
