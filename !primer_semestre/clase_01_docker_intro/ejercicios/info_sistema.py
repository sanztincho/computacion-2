#!/usr/bin/env python3
"""
Script que muestra información del sistema:
- Versión de Python
- Sistema operativo (nombre, versión)
- Cantidad de CPUs disponibles
- Memoria disponible
- Variables de entorno que empiecen con "PYTHON"
"""

import sys
import platform
import os
import psutil

def obtener_info_sistema():
    """Obtiene y muestra la información del sistema."""
    
    print("=" * 60)
    print("INFORMACIÓN DEL SISTEMA")
    print("=" * 60)
    
    # Versión de Python
    print(f"\n📌 Versión de Python:")
    print(f"   {sys.version}")
    print(f"   Implementación: {platform.python_implementation()}")
    
    # Sistema operativo
    print(f"\n📌 Sistema Operativo:")
    print(f"   Sistema: {platform.system()}")
    print(f"   Versión: {platform.release()}")
    print(f"   Plataforma: {platform.platform()}")
    
    # CPUs disponibles
    print(f"\n📌 Procesadores:")
    cpu_count = os.cpu_count()
    print(f"   CPUs disponibles: {cpu_count}")
    
    # Memoria disponible
    print(f"\n📌 Memoria:")
    try:
        import psutil
        mem = psutil.virtual_memory()
        print(f"   Total: {mem.total / (1024**3):.2f} GB")
        print(f"   Disponible: {mem.available / (1024**3):.2f} GB")
        print(f"   Usada: {mem.used / (1024**3):.2f} GB")
        print(f"   Porcentaje: {mem.percent}%")
    except ImportError:
        print("   ⚠️  psutil no está instalado")
        print("      Intentando con información básica...")
        try:
            # Alternativa sin psutil (parcial)
            with open('/proc/meminfo', 'r') as f:
                meminfo = dict((i.split()[0].rstrip(':'), int(i.split()[1])) 
                              for i in f.readlines())
                mem_total_kb = meminfo.get('MemTotal', 0)
                mem_available_kb = meminfo.get('MemAvailable', 0)
                print(f"   Total: {mem_total_kb / (1024**2):.2f} GB")
                print(f"   Disponible: {mem_available_kb / (1024**2):.2f} GB")
        except:
            print("   No se pudo obtener información de memoria")
    
    # Variables de entorno que empiezan con PYTHON
    print(f"\n📌 Variables de entorno con 'PYTHON':")
    python_vars = {k: v for k, v in os.environ.items() if k.startswith('PYTHON')}
    
    if python_vars:
        for key, value in sorted(python_vars.items()):
            # Truncar valores muy largos
            value_str = str(value)
            if len(value_str) > 70:
                value_str = value_str[:67] + "..."
            print(f"   {key} = {value_str}")
    else:
        print("   No hay variables de entorno que empiecen con 'PYTHON'")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    obtener_info_sistema()
