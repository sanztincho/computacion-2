#!/usr/bin/env python3
"""
Inspector de archivos - Herramienta para mostrar información detallada sobre archivos
"""

import sys
import os
import stat
import pwd
import grp
from pathlib import Path
from datetime import datetime


def get_file_type(st):
    """Determina el tipo de archivo basado en los bits de modo"""
    mode = st.st_mode
    
    if stat.S_ISREG(mode):
        return "archivo regular"
    elif stat.S_ISDIR(mode):
        return "directorio"
    elif stat.S_ISLNK(mode):
        return "enlace simbólico"
    elif stat.S_ISBLK(mode):
        return "dispositivo de bloques"
    elif stat.S_ISCHR(mode):
        return "dispositivo de caracteres"
    elif stat.S_ISFIFO(mode):
        return "tubería (FIFO)"
    elif stat.S_ISSOCK(mode):
        return "socket"
    else:
        return "desconocido"


def get_permissions(st):
    """Retorna los permisos en formato legible (rwxr-xr-x) y octal"""
    mode = st.st_mode & 0o777
    
    # Formato legible
    readable = ""
    # Usuario
    readable += "r" if mode & stat.S_IRUSR else "-"
    readable += "w" if mode & stat.S_IWUSR else "-"
    readable += "x" if mode & stat.S_IXUSR else "-"
    # Grupo
    readable += "r" if mode & stat.S_IRGRP else "-"
    readable += "w" if mode & stat.S_IWGRP else "-"
    readable += "x" if mode & stat.S_IXGRP else "-"
    # Otros
    readable += "r" if mode & stat.S_IROTH else "-"
    readable += "w" if mode & stat.S_IWOTH else "-"
    readable += "x" if mode & stat.S_IXOTH else "-"
    
    # Formato octal
    octal = f"{mode:o}"
    
    return readable, octal


def get_owner_info(st):
    """Retorna nombre de usuario y grupo"""
    try:
        owner_name = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner_name = "desconocido"
    
    try:
        group_name = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group_name = "desconocido"
    
    return owner_name, group_name


def format_size(size):
    """Convierte bytes a formato legible (KB, MB, GB)"""
    units = ["bytes", "KB", "MB", "GB", "TB"]
    size_float = float(size)
    
    for unit in units:
        if size_float < 1024:
            if unit == "bytes":
                return f"{int(size_float)} bytes ({int(size_float)} bytes)"
            else:
                return f"{size_float:.2f} {unit} ({size} bytes)"
        size_float /= 1024
    
    return f"{size_float:.2f} PB ({size} bytes)"


def get_symlink_target(path):
    """Obtiene el destino de un enlace simbólico"""
    try:
        return os.readlink(path)
    except OSError:
        return None


def count_directory_contents(path):
    """Cuenta cuántos elementos hay dentro de un directorio"""
    try:
        return len(os.listdir(path))
    except OSError:
        return None


def format_timestamp(timestamp):
    """Convierte timestamp a formato legible"""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def inspect_file(file_path):
    """Inspecciona un archivo y muestra su información"""
    
    # Obtener el path absoluto SIN seguir symlinks
    path = Path(file_path).absolute()
    
    # Intentar obtener información del archivo (sin seguir symlinks)
    try:
        st = os.lstat(path)
    except OSError as e:
        print(f"Error al leer '{file_path}': {e}", file=sys.stderr)
        return False
    
    file_type = get_file_type(st)
    readable_perms, octal_perms = get_permissions(st)
    owner_name, group_name = get_owner_info(st)
    
    # Encabezado
    print(f"Archivo: {path}")
    
    # Tipo y enlace simbólico
    if file_type == "enlace simbólico":
        target = get_symlink_target(path)
        print(f"Tipo: {file_type} -> {target}")
    else:
        print(f"Tipo: {file_type}")
    
    # Tamaño (solo para archivos regulares y dispositivos)
    if file_type == "archivo regular":
        print(f"Tamaño: {format_size(st.st_size)}")
    elif file_type == "directorio":
        size_bytes = st.st_size
        print(f"Tamaño: {format_size(size_bytes)}")
        count = count_directory_contents(path)
        if count is not None:
            print(f"Contenido: {count} elementos")
    elif file_type in ["dispositivo de bloques", "dispositivo de caracteres"]:
        # Para dispositivos, mostrar major/minor numbers
        dev_major = os.major(st.st_rdev)
        dev_minor = os.minor(st.st_rdev)
        print(f"Dispositivo: mayor={dev_major}, menor={dev_minor}")
    
    # Permisos
    print(f"Permisos: {readable_perms} ({octal_perms})")
    
    # Propietario
    print(f"Propietario: {owner_name} (uid: {st.st_uid})")
    print(f"Grupo: {group_name} (gid: {st.st_gid})")
    
    # Inodo
    print(f"Inodo: {st.st_ino}")
    
    # Enlaces duros
    print(f"Enlaces duros: {st.st_nlink}")
    
    # Timestamps
    print(f"Creación: {format_timestamp(st.st_ctime)}")
    print(f"Última modificación: {format_timestamp(st.st_mtime)}")
    print(f"Último acceso: {format_timestamp(st.st_atime)}")
    
    return True


def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python inspector.py <ruta_archivo>", file=sys.stderr)
        print("\nEjemplos:", file=sys.stderr)
        print("  python inspector.py /etc/passwd", file=sys.stderr)
        print("  python inspector.py /bin", file=sys.stderr)
        print("  python inspector.py /dev/null", file=sys.stderr)
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = inspect_file(file_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
