def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'

    Parameters
    ----------
    b : int
        size in bytes
    factor : int, optional
        conversion factor, by default 1024
    suffix : str, optional
        suffix to attach to the converted size, by default "B"
        possible values are: ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB']
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"


def rename_dir(path, src, dst):
    """Rename src directory to dst directory in path. for example:
    doesn't matter where src is in the path, it will be replaced by dst
    rename_dir('/home/src/subdir', 'src', 'dst') -> '/home/dst/subdir'

    Parameters
    ----------
    path : str
        path to rename
    src : str
        source directory name
    dst : str
        destination directory to rename source to

    Returns
    -------
    path : Path(path)
        path with src replaced by dst
    """
    from pathlib import Path
    # convert to list so that we can change elements
    parts = list(path.parts)

    # replace part that matches src with dst
    parts[parts.index(src)] = dst

    return Path(*parts)

def dir_empty(path):
    """Delete empty directories recursively starting from the path supplied"""
    from pathlib import Path
    path = Path(path)
    empty = True
    for item in path.glob('*'):
        if item.is_file():
            empty = False
        if item.is_dir() and not dir_empty(item):
            empty = False
    if empty:
        path.rmdir()  # Remove if you just want to have the result
    return empty