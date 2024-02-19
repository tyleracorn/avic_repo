from pathlib import Path
from .utils.file_utils import get_size_format, rename_dir
from tqdm.notebook import tqdm
import shutil
import pandas as pd
from .image_compression import MultiImageCompression
from .utils.logger import ClassWithLogger
import tempfile


_ic_failed = 'Failed'
# _ic_compressed = 'Compressed'
# _ic_not_compressed = 'NOT Compressed'


def _new_output_zfile(zfile, manga_dir, save_dir, save_cbz=True,
                      words_to_drop=['[English]', '[Digital]', '(English)']):
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
        list of words to drop from the zip file name,
        by default ['[English]', '[Digital]', '(English)']
    save_cbz : bool, optional
        save as zip file renamed to cbz for comic readers, by default True
    """

    if str(manga_dir) == '.':
        new_zfl = save_dir.joinpath(zfile.name)
    else:
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

    return manga_int_dir


class MultiMangaCompression(ClassWithLogger):
    def __init__(self, manga_dir, save_dir, interim_dir, error_dir='manga_compression_errors',
                 manga_formats=['.zip', '.cbz'], log_file='manga_log.txt', external_logger=False):
        """Compress multiple manga files in a directory to new zip files in a new directory.

        Parameters
        ----------
        manga_dir : Path
            path to manga directory
        save_dir : Path
            path to save directory that will contain the new zip files
        interim_dir : Path
            path to interim directory where the manga files will be extracted to during compression
        error_dir : str, optional
            path to save files that errors occured in compression,
            by default 'manga_compression_errors'
        log_file : str, optional
            path to save log file, by default 'manga_log.txt'
        external_logger : logger, optional
            external logger to use, by default None
        """
        super().__init__(name='MultiMangaCompression', log_file=log_file, logger=external_logger)
        self.manga_dir = Path(manga_dir)
        self.save_dir = Path(save_dir)
        self.interim_dir = Path(interim_dir)
        self.error_dir = Path(error_dir)
        for dr in [self.save_dir, self.interim_dir, self.error_dir]:
            if dr.is_dir() is False:
                dr.mkdir(parents=True)

        self.manga_compressor = False
        self.manga_formats = manga_formats

        self.manga_files = [fl for fl in self.manga_dir.glob('*') if fl.is_file()]
        self.manga_files = [fl for fl in self.manga_files if fl.suffix in self.manga_formats]
        self.debug = False

        self.n_mangas = len(self.manga_files)
        self.total_size_bytes = sum([fl.stat().st_size for fl in self.manga_files])
        self.total_size = get_size_format(self.total_size_bytes)
        self.compress_size_bytes = 0
        self.compress_size = 0

    def set_debug(self, debug=True):
        """Set the debug mode for the class

        Parameters
        ----------
        debug : bool, optional
            debug mode, by default True
        """
        self.debug = debug

    def _compress_single_manga(self, manga_file):
        """Compress a single manga file

        Parameters
        ----------
        manga_file : Path
            path to manga file
        """
        self.manga_compressor = MangaCompress(manga_file, external_logger=self.logger)
        self.manga_compressor.set_directories(interim_dir=self.interim_dir,
                                              new_save_dir=self.save_dir,
                                              error_dir=self.error_dir)

        if self.debug:
            self.manga_compressor.set_debug(True)

        self.manga_compressor.compress_manga_images(progress_bar=False)
        self.compress_size_bytes += self.manga_compressor.new_zfl.stat().st_size
        self.compress_size = get_size_format(self.compress_size_bytes)

    def compress_mangas(self, progress_bar=True):
        """Compress the manga files to new zip files in a new directory

        Parameters
        ----------
        progress_bar : bool, optional
            show progress bar, by default True
        """
        if progress_bar:
            for mid, manga_file in enumerate(tqdm(self.manga_files, desc='Mangas')):
                self._compress_single_manga(manga_file)
        else:
            for manga_file in self.manga_files:
                self._compress_single_manga(manga_file)


class MangaCompress(ClassWithLogger):
    def __init__(self, manga_file, log_file='manga_log.txt',
                 external_logger=False):
        """compress a manga file to a new zip file in a new directory.

        Parameters
        ----------
        manga_file : Path
            path to manga file
        save_dir : Path
            path to save directory that will contain the new zip file
        log_file : str, optional
            path to save log file, by default 'manga_log.txt'
        external_logger : logger, optional
            external logger to use, by default None
        """
        from .utils.file_utils import unzip_file, zip_manga_dir
        super().__init__(name='MangaCompress', log_file=log_file, logger=external_logger)
        self.manga_file = Path(manga_file)
        self.save_cbz = True

        self.mi_compress = False

        self.unzip_file = unzip_file
        self.zip_manga_dir = zip_manga_dir

        self.unzip_dir = False
        self.compress_dir = False
        self.debug = False

    def _clenup_temoporary_dirs(self):
        if self.unzip_dir is not False:
            self.unzip_dir.cleanup()
        if self.compress_dir is not False:
            self.compress_dir.cleanup()

    def set_debug(self, debug=True):
        """Set the debug mode for the class

        Parameters
        ----------
        debug : bool, optional
            debug mode, by default True
        """
        self.debug = debug

    def set_directories(self, interim_dir, new_save_dir=False, error_dir='manga_compression_errors',
                        flname_words_to_drop=['[English]', '[Digital]', '(English)']):
        """Set the interim and error directories for compressing the manga file

        Parameters
        ----------
        interim_dir : Path
            path to interim directory where the manga files will be extracted to during compression
        new_save_dir : Path
            path to save directory that will contain the new zip file
        error_dir : str, optional
            path to save files that errors occured in compression,
            by default 'manga_compression_errors'
        flname_words_to_drop : list, optional
            list of words to drop from the zip file name, by default
            for example ['[English]', '[Digital]', '(English)']
        """
        self.interim_dir = Path(interim_dir)
        self.error_dir = Path(error_dir)
        if self.interim_dir.is_dir() is False:
            self.interim_dir.mkdir(parents=True)
        if new_save_dir is not False:
            self.save_dir = Path(new_save_dir)
            if self.save_dir.is_dir() is False:
                self.save_dir.mkdir(parents=True)
        else:
            self.save_dir = self.manga_file.parent
        self.flname_words_to_drop = flname_words_to_drop

    def set_paramaters(self, save_cbz=True):
        """Set the parameters for compressing the manga file

        Parameters
        ----------
        save_cbz : bool, optional
            save as zip file renamed to cbz for comic readers, by default True
        """
        self.save_cbz = save_cbz

    def _setup_files_paths(self):
        """Setup the file paths for the manga file"""
        self.new_zfl = _new_output_zfile(self.manga_file,
                                         self.manga_file.parent,
                                         self.save_dir,
                                         words_to_drop=self.flname_words_to_drop,
                                         save_cbz=self.save_cbz)
        self._clenup_temoporary_dirs()
        self.unzip_dir = tempfile.TemporaryDirectory(dir=self.interim_dir, prefix='manga_unzip_')
        self.compress_dir = tempfile.TemporaryDirectory(dir=self.interim_dir, prefix='manga_comp_')

    def _shutil_uncompressed_files(self):
        """move over uncompressed files from unzip directory to compress directory.
        This will catch any files that were not compressed when the compression failed or
        that were not image files"""

        src_path = Path(self.unzip_dir.name)
        dst_path = Path(self.compress_dir.name)

        src_files = [fl for fl in src_path.rglob('*') if fl.is_file()]
        dst_files = [fl for fl in dst_path.rglob('*') if fl.is_file()]
        dst_files_stems = [fl.stem for fl in dst_files]

        for fl in src_files:
            if fl.stem not in dst_files_stems:
                shutil.move(fl, dst_path.joinpath(fl.name))

    def _copy_failed_files(self):
        """check the _ic_stats for failed files and copy them to the error directory"""
        if self._ic_stats is not False:
            mask_failed = self._ic_stats['Status'] == _ic_failed
            if mask_failed.sum() > 0:
                err_dir = self.error_dir.joinpath(self.manga_file.stem)
                if err_dir.is_dir() is False:
                    err_dir.mkdir(parents=True)
                failed_files = self._ic_stats[mask_failed]['Image'].tolist()
                for fl in failed_files:
                    shutil.copy(fl, self.error_dir)

    def _check_for_subdirectories(self):
        """Check if there are subdirectories in the unzip directory and print name of zip file"""
        unzip_dir = Path(self.unzip_dir.name)
        subdirs = [fl for fl in unzip_dir.glob('*') if fl.is_dir()]
        if len(subdirs) > 0:
            self.logger.warning(f"Subdirectories found in {self.manga_file.name}")
            print(f"Subdirectories found in {self.manga_file.name}")

    def compress_manga_images(self, progress_bar=True):
        """Uncompress the manga file, compress the images and save the new zip file"""
        if self.logger is not False:
            self.logger.info(f"Compressing {self.manga_file.name}")
        self._setup_files_paths()

        self.unzip_file(self.manga_file, extract_dir=self.unzip_dir.name)

        self.mi_compress = MultiImageCompression(stats_fl=False,
                                                 overwrite=False,
                                                 log_file=False,
                                                 external_logger=self.logger)
        self.mi_compress.set_dir(self.unzip_dir.name,
                                 compress_dir=self.compress_dir.name,
                                 processed_dir=self.unzip_dir.name)

        ic_stats = self.mi_compress.compress_files(progress_bar=progress_bar)
        self._ic_stats = ic_stats

        self._check_for_subdirectories()
        self._copy_failed_files()
        self._shutil_uncompressed_files()

        if self.debug:
            delete_dir = False
        else:
            delete_dir = True
        self.zip_manga_dir(zdir=self.compress_dir.name,
                           filename=self.new_zfl,
                           as_cbz=self.save_cbz,
                           delete_dir=delete_dir)
        if self.debug is False:
            self._clenup_temoporary_dirs()
