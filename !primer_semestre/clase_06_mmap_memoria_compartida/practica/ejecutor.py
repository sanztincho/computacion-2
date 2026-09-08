#!/usr/bin/env python3
"""
Script ejecutor para todos los ejercicios
Ejecuta secuencialmente y muestra un resumen de resultados
"""
import sys
import subprocess
import os
from pathlib import Path

EJERCICIOS = [
    ("ejercicio_1_mmap_basico.py", "Explorando mmap sobre archivos"),
    ("ejercicio_2_mmap_binario.py", "mmap como estructura de datos binaria"),
    ("ejercicio_3_mmap_anonimo.py", "mmap anónimo entre padre e hijo"),
    ("ejercicio_4_mmap_multiprocessing.py", "mmap con multiprocessing"),
    ("ejercicio_5_value_array.py", "Value y Array compartidos"),
    ("ejercicio_6_shared_memory.py", "SharedMemory y ShareableList"),
]

def print_header(title):
    """Imprime encabezado formateado."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def print_footer(success):
    """Imprime pie de página."""
    status = "✓ EXITOSO" if success else "✗ FALLÓ"
    print(f"\n{status}\n")

def main():
    """Ejecuta todos los ejercicios."""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print_header("EJECUTOR DE EJERCICIOS - mmap y Memoria Compartida")
    
    resultados = []
    
    for i, (archivo, descripcion) in enumerate(EJERCICIOS, 1):
        filepath = script_dir / archivo
        
        if not filepath.exists():
            print(f"❌ Ejercicio {i}: {archivo} NO ENCONTRADO")
            resultados.append((i, archivo, False))
            continue
        
        print_header(f"EJERCICIO {i}: {descripcion}")
        print(f"Archivo: {archivo}")
        print(f"Ruta: {filepath}\n")
        
        try:
            # Ejecutar con timeout de 30 segundos
            resultado = subprocess.run(
                [sys.executable, str(filepath)],
                capture_output=False,
                timeout=30
            )
            
            exitoso = resultado.returncode == 0
            if exitoso:
                print_footer(True)
            else:
                print(f"\n❌ El ejercicio terminó con código de salida: {resultado.returncode}\n")
            
            resultados.append((i, archivo, exitoso))
            
        except subprocess.TimeoutExpired:
            print(f"\n❌ El ejercicio tardó demasiado (>30s)\n")
            resultados.append((i, archivo, False))
        except Exception as e:
            print(f"\n❌ Error ejecutando ejercicio: {e}\n")
            resultados.append((i, archivo, False))
    
    # Resumen final
    print_header("RESUMEN FINAL")
    
    print(f"{'Ej':<4} {'Archivo':<40} {'Estado':<12}")
    print("-" * 60)
    
    exitosos = 0
    for num, archivo, exitoso in resultados:
        estado = "✓ OK" if exitoso else "✗ FALLÓ"
        if exitoso:
            exitosos += 1
        print(f"{num:<4} {archivo:<40} {estado:<12}")
    
    print("-" * 60)
    print(f"Total: {exitosos}/{len(resultados)} ejercicios completados")
    
    if exitosos == len(resultados):
        print("\n🎉 ¡TODOS LOS EJERCICIOS COMPLETADOS EXITOSAMENTE!")
    else:
        print(f"\n⚠️  {len(resultados) - exitosos} ejercicio(s) fallaron")
    
    print("\n" + "=" * 70)
    print("Para más detalles, ver DOCUMENTACION.md")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
