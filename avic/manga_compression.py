from pathlib import Path
from .utils.file_utils import get_size_format

def _new_output_zfile(zfile, manga_dir, save_dir, words_to_drop=['[English]', '[Digital]', '(English)'],
                      save_cbz=True):
    """
    Get a new output zip file name based on the original zip file name but in a new directory.
    remove words_to_drop from the zip file name.

    Parameters
    ----------
    zfile : Path
        path to zip file
    manga_dir : Path
        path to manga directory where the manga file is stored
    save_dir : Path
        path to save directory that will contain the new zip file
    words_to_drop : list, optional
        list of words to drop from the zip file name, by default ['[English]', '[Digital]', '(English)']
    save_cbz : bool, optional
        save as zip file renamed to cbz for comic readers, by default True
    """
    from .utils.file_utils import rename_dir
    new_zfl = rename_dir(zfile,
                         src=str(manga_dir),
                         dst=str(save_dir))
    shrt_nme = new_zfl.stem
    for word in words_to_drop:
        shrt_nme = shrt_nme.replace(word, '')
    shrt_nme = shrt_nme.strip()
    new_zfl = new_zfl.with_stem(shrt_nme)
    if save_cbz:
        new_zfl = new_zfl.with_suffix('.cbz')
    if new_zfl.parent.is_dir() is False:
        new_zfl.parent.mkdir(parents=True)
    return new_zfl

def _get_manga_unzip_dir(new_zipfile, save_dir, interim_dir):
    """
    Get the interim manga directory where the manga files will be extracted to.
    The interim manga directory will be the same name as the zip file but without the zip extension.

    Example
    -------
    new_zipfile = /home/user/converted_mangas/author/manga_name.zip
    save_dir = /home/user/converted_mangas
    interim_dir = /home/user/interim_dir
    return zip_file_dir = /home/user/interim_dir/author/manga_name

    Parameters
    ----------
    new_zipfile : Path
        path to the new zip file
    save_dir : Path
        path to the save directory
    interim_dir : Path
        path to the interim directory where the manga files will be extracted to
    """
    from .utils.file_utils import rename_dir
    manga_int_dir = rename_dir(new_zipfile,
                               src=str(save_dir),
                               dst=str(interim_dir))
    manga_int_dir = manga_int_dir.with_name(manga_int_dir.stem)
    if manga_int_dir.is_dir() is False:
        manga_int_dir.mkdir()
    return manga_int_dir

def get_zip_file_dicts(manga_dir, interim_dir, save_dir, manga_suffixes=['.zip', '.cbz'],
                       words_to_drop=['[English]', '[Digital]', '(English)'], save_cbz=True):
    """
    Get a dictionary of zip files the cooresponding interim directory for exctracting the zip files
    to. during compression and the new zip file name for saveing the converted zip file to.

    Parameters
    ----------
    manga_dir : Path
        path to manga directory where the manga file is stored
    interim_dir : Path
        path to interim directory where the manga files will be extracted to during compression
    save_dir : Path
        path to save directory that will contain the new zip file
    manga_suffixes : list, optional
        list of manga file suffixes, by default ['.zip', '.cbz']
    words_to_drop : list, optional
        list of words to drop from the zip file name, by default ['[English]', '[Digital]', '(English)']
    save_cbz : bool, optional
        save as zip file renamed to cbz for comic readers, by default True

    Returns
    -------
    zfile_dict : dict
        {zip_file: {'save_file': Path,
                    'manga_interim_dir': Path}
        }
    """
    zip_files = [fl for fl in Path(manga_dir).rglob('*') if fl.is_file()]
    zip_files = [fl for fl in zip_files if fl.suffix.lower() in manga_suffixes]

    zfile_dict = {}
    for fl in zip_files:
        new_zfl = _new_output_zfile(fl,
                                    manga_dir,
                                    save_dir,
                                    words_to_drop=words_to_drop,
                                    save_cbz=save_cbz)
        manga_interim_dir = _get_manga_unzip_dir(new_zfl,
                                                 save_dir,
                                                 interim_dir)


        zfile_dict[fl] = {'save_file': new_zfl,
                          'manga_interim_dir':manga_interim_dir}
    return zfile_dict


def compress_manga_images(manga_dir, interim_dir, save_dir, manga_suffixes=['.zip', '.cbz'],
                          words_to_drop=['[English]', '[Digital]', '(English)'], save_cbz=True,
                          delete_interim=True, compression_stats_fl='manga_compression_stats.csv'):
    """
    Compress manga images in a zip file to a new zip file in a new directory.
    The new zip file will be renamed to the original zip file name but with the words_to_drop removed.
    The interim directory will be the same name as the zip file but without the zip extension.
    The interim directory will be deleted after the compression is complete.

    Parameters
    ----------
    manga_dir : Path
        path to manga directory where the manga file is stored
    interim_dir : Path
        path to interim directory where the manga files will be extracted to during compression
    save_dir : Path
        path to save directory that will contain the new zip file
    manga_suffixes : list, optional
        list of manga file suffixes, by default ['.zip', '.cbz']
    words_to_drop : list, optional
        list of words to drop from the zip file name, by default ['[English]', '[Digital]', '(English)']
    save_cbz : bool, optional
        save as zip file renamed to cbz for comic readers, by default True
    delete_interim : bool, optional
        delete the interim directory after the compression is complete, by default True
    """
    from .utils.file_utils import unzip_file, zip_manga_dir
    from .image_compression import get_files_to_compress, compress_files_subdir
    print(f"Getting manga files and building dictionary")
    zfile_dict = get_zip_file_dicts(manga_dir,
                                    interim_dir,
                                    save_dir,
                                    manga_suffixes=manga_suffixes,
                                    words_to_drop=words_to_drop,
                                    save_cbz=save_cbz)
    print(f"Unzipping {len(zfile_dict)} manga files")
    for zfile in zfile_dict:
        unzip_file(zfile, extract_dir=zfile_dict[zfile]['manga_interim_dir'])

    print(f"  Compressing {len(zfile_dict)} manga files")
    compress_files_dict = get_files_to_compress(interim_dir)

    _ = compress_files_subdir(compress_files_dict,
                              starting_dir=interim_dir,
                              to_jpg=False,
                              overwrite=True)

    zcomp_stats_list = []
    print(f"  Zipping {len(zfile_dict)} manga files")
    for zfile in zfile_dict:

        zip_manga_dir(zdir=zfile_dict[zfile]['manga_interim_dir'],
                      filename=zfile_dict[zfile]['save_file'],
                      as_cbz=save_cbz,
                      delete_dir=delete_interim)

        old_size = zfile.stat().st_size
        new_size = zfile_dict[zfile]['save_file'].stat().st_size
        if old_size == new_size:
            saving_diff_str = '--'
        else:
            saving_diff = (old_size - new_size)/old_size
            saving_diff_str = f"{saving_diff:.1%}"

        results = pd.DataFrame({'Manga': [zfile.stem],
                                'Manga_size': [get_size_format(old_size)],
                                'New_size': [get_size_format(new_size)],
                                'Compress %': [saving_diff_str],
                                    })
        zcomp_stats_list.append(results)
        if compression_stats_fl is not None or compression_stats_fl is not False:
            zcomp_stats = pd.concat(zcomp_stats_list, ignore_index=True)
            zcomp_stats.to_csv(compression_stats_fl, index=False)

    return outstats
