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

    src = str(src)
    dst = str(dst)
    # replace part that matches src with dst
    parts[parts.index(src)] = dst

    return Path(*parts)


def delete_empty_dir(path):
    """Delete empty directories recursively starting from the path supplied"""
    from pathlib import Path
    path = Path(path)
    empty = True
    for item in path.glob('*'):
        if item.is_file():
            empty = False
        if item.is_dir() and not delete_empty_dir(item):
            empty = False
    if empty:
        path.rmdir()  # Remove if you just want to have the result
    return empty


def unzip_file(file, extract_dir=None):
    """Unzip file. If extract_dir is False, then extract to the same directory as the file.

    Parameters
    ----------
    file : Path
        path to file to unzip
    extract_dir : bool, optional
        extract to another directory. by default False"""
    import zipfile
    with zipfile.ZipFile(file, "r") as zip_ref:
        zip_ref.extractall(path=extract_dir)


def zip_manga_dir(zdir, filename=None, as_cbz=False, delete_dir=False):
    """Zip manga directory into a manga zip file. If as_cbz is True, then save as a cbz file.

    Parameters
    ----------
    zdir : Path
        path to manga directory
    filename : str, optional
        name of zip file, by default None in which case the name of the zip file will be the same
        as the directory
    as_cbz : bool, optional
        save as cbz file, by default False
    delete_dir : bool, optional
        delete the directory after zipping, by default False
    """
    import zipfile
    import shutil
    zdir = Path(zdir)
    if filename is None:
        filename = zdir
    else:
        filename = Path(filename)
    if as_cbz:
        filename = filename.with_suffix('.cbz')
    else:
        filename = filename.with_suffix('.zip')

    assert zdir.is_dir(), f"{zdir} is not a directory"
    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for entry in zdir.rglob("*"):
            zipf.write(entry, entry.relative_to(zdir))

    if delete_dir:
        shutil.rmtree(zdir)