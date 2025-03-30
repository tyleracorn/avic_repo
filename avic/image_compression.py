from PIL import Image
from pathlib import Path
import pandas as pd
from .utils.file_utils import get_size_format, rename_dir
from tqdm.notebook import tqdm
import shutil
from PIL import UnidentifiedImageError
from .utils.logger import ClassWithLogger

_failed = 'Failed'
_compressed = 'Compressed'
_not_compressed = 'NOT Compressed'
_s = ' '
_s2 = _s*2
_s4 = _s*4
_s6 = _s*6


def get_files_to_compress_recursive(main_dir, img_suffixes=['.jpg', '.jpeg', '.png']):
    """
    get list of image files to compress from a directory, also get all subdirectories
    that can then be used to iterate through all subdirectories

    Parameters
    ----------
    main_dir : str
        directory to search for files
    img_suffixes : list, optional
        list of image suffixes to search for. The default is ['.jpg', 'jpeg', '.png'].

    Returns
    -------
    files: list
        list of files
    sub_directories: list
        list of subdirectories
    """
    img_suffixes = [suffix.lower() for suffix in img_suffixes]
    sub_directories = [folder for folder in Path(main_dir).glob('*') if folder.is_dir()]
    files = []
    files = [fl for fl in main_dir.glob('*') if fl.is_file()]
    files = [fl for fl in files if fl.suffix.lower() in img_suffixes]

    return files, sub_directories


def _get_subdir_images_to_compress(subdir_file_dict, subdir, overwrite, starting_dir, compress_dir,
                                   processed_dir):
    """
    get list of image files to compress from a directory. This will iterate through all
    subdirectories

    Parameters
    ----------
    subdir_file_dict : dict
        dictionary of subdirectories and files to compress. This is the output of
        get_files_to_compress
    subdir : str
        subdirectory to compress
    overwrite : bool
        if True, then it will overwrite the original file
    starting_dir : str
        directory where the files are located
    compress_dir : str, optional
        directory where the compressed files will be saved. The default is 'compressed'.
    processed_dir : str, optional
        directory where the processed files will be moved to. The default is 'processed'.

    """
    fl_compress_dict = {}
    files = []
    subfiles = subdir_file_dict[subdir]['subfiles']
    for fl in subfiles:
        if overwrite is False:
            comp_fl = rename_dir(fl, starting_dir, compress_dir)
            proc_fl = rename_dir(fl, starting_dir, processed_dir)
            if comp_fl.parent.is_dir() is False:
                comp_fl.parent.mkdir(parents=True)
            if proc_fl.parent.is_dir() is False:
                proc_fl.parent.mkdir(parents=True)
        else:
            comp_fl = fl
            proc_fl = False
        fl_compress_dict[fl] = {'comp_fl': comp_fl, 'proc_fl': proc_fl}
        files.append(fl)
    return fl_compress_dict, files


class MultiImageCompression(ClassWithLogger):
    def __init__(self,
                 img_suffixes=['.jpg', 'jpeg', '.png'], stats_fl='compression_stats.csv',
                 to_jpg=True, overwrite=False, log_file='log.txt', external_logger=False):
        """
        Compress all images in a directory and save them to a new directory.

        nuances:
        starting_dir is the directory where the files are located. The compressed_dir is used
        to rename the file path. For example, if the file is located in
        'images/2020/01/01/image.jpg' and the compressed_dir is 'compressed', then the new file
        path will be 'compressed/2020/01/01/image.jpg'

        same goes for the processed_dir.

        warning. the rename function will rename all matching strings in the path. For example,
        if the starting_dir is 'images' and it shows up twice in the path, then it will rename
        both of them. for example, if the file is located in 'images/2020/01/01/images/image.jpg'
        and the starting_dir is 'images', then the new file path will be
        'compressed/2020/01/01/compressed/image.jpg'

        Parameters
        ----------
        subdir_file_dict : dict
            dictionary of subdirectories and files to compress. This is the output of
            get_files_to_compress
        starting_dir : str
            directory where the files are located
        compress_dir : str, optional
            directory where the compressed files will be saved. The default is 'compressed'.
        processed_dir : str, optional
            directory where the processed files will be saved. The default is 'processed'.
        img_suffixes : list, optional
            list of image suffixes to search for. The default is ['.jpg', 'jpeg', '.png'].
            any file that doesn't match these suffixes will be ignored.

        Outline
        -------
        1. get list of files to compress
        2. compress files
            2a. get new size ratio
            2b. get quality
            2c. compress image
            2d. check if new image size is less than old image size
            2e. if new image size is less than old image size, then save the image
            2f. if new image size is greater than old image size, then try to compress again
        3. save compression stats
        """
        super().__init__(name='MultiImageCompression', log_file=log_file, logger=external_logger)
        self.starting_dir = False
        self.compress_dir = False
        self.processed_dir = False
        self.img_suffixes = img_suffixes
        self.stats_fl = stats_fl
        self.to_jpg = to_jpg
        self.overwrite = overwrite

        self.image_compressor = ImageCompress(new_size_ratio='auto',
                                              quality='auto',
                                              to_jpg=self.to_jpg,
                                              n_attemps=3,
                                              log_file=False,
                                              external_logger=self.logger)

    def set_dir(self, starting_dir, compress_dir='compressed', processed_dir='processed',
                failed_dir='failed'):
        """
        Set the directories for the image compression

        nuances:
        starting_dir is the directory where the files are located. The compressed_dir is used
        to rename the file path. For example, if the file is located in
        'images/2020/01/01/image.jpg' and the compressed_dir is 'compressed', then the new file
        path will be 'compressed/2020/01/01/image.jpg'

        same goes for the processed_dir.

        warning. the rename function will rename all matching strings in the path. For example,
        if the starting_dir is 'images' and it shows up twice in the path, then it will rename
        both of them. for example, if the file is located in 'images/2020/01/01/images/image.jpg'
        and the starting_dir is 'images', then the new file path will be
        'compressed/2020/01/01/compressed/image.jpg'

        Parameters
        ----------
        starting_dir : str
            directory where the files are located
        compress_dir : str, optional
            directory where the compressed files will be saved. The default is 'compressed'.
        processed_dir : str, optional
            directory where the processed files will be saved. The default is 'processed'.
        """
        self.starting_dir = Path(starting_dir)
        self.compress_dir = Path(compress_dir)
        self.processed_dir = Path(processed_dir)
        self.failed_dir = Path(failed_dir)
        if self.logger is not False:
            self.logger.info(f"starting_dir: {self.starting_dir}")
            self.logger.info(f"compress_dir: {self.compress_dir}")
            self.logger.info(f"processed_dir: {self.processed_dir}")

    def _get_compress_paths(self, files):
        """
        get list of image files to compress from a directory. This will iterate through all
        subdirectories

        Parameters
        ----------
        files : list
            list of files to compress

        """
        self.logger.info(f"Getting compress paths for {len(files)} files")
        fl_compress_dict = {}
        for fl in files:
            fail_fl = rename_dir(fl, self.starting_dir, self.failed_dir)
            if self.overwrite is False:
                comp_fl = rename_dir(fl,
                                     self.starting_dir,
                                     self.compress_dir)
                proc_fl = rename_dir(fl,
                                     self.starting_dir,
                                     self.processed_dir)
                if comp_fl.parent.is_dir() is False:
                    comp_fl.parent.mkdir(parents=True)
                if proc_fl.parent.is_dir() is False:
                    proc_fl.parent.mkdir(parents=True)
            else:
                comp_fl = fl
                proc_fl = False
            fl_compress_dict[fl.name] = {
                'fl': fl,
                'comp_fl': comp_fl,
                'proc_fl': proc_fl,
                'fail_fl': fail_fl,
                }
        return fl_compress_dict

    def _compress_singlesubdir_images(self, files, folder_name, progress_bar=True):
        """
        compress the files in a subdirectory

        Parameters
        ----------
        files : list
            list of files to compress
        folder_name : str
            name of the subdirectory which is used in the progress bar if progress_bar is True
        progress_bar : bool, optional
            if True, then it will show a progress bar. The default is True.
        """
        self.logger.info((f"Compressing {len(files)} files in {folder_name}. "
                          f"progress_bar={progress_bar}"))
        compres_stats_list = []
        comp_paths = self._get_compress_paths(files)

        if progress_bar:
            for flid, fl in enumerate(tqdm(files, desc=f'{folder_name}: ')):
                comp_fl = comp_paths[fl.name]['comp_fl']
                proc_fl = comp_paths[fl.name]['proc_fl']
                fail_dir = comp_paths[fl.name]['fail_fl'].parent
                stats, cstatus = self.image_compressor.compress_image(
                    fl,
                    export_path=comp_fl,
                    fail_dir=fail_dir,
                    )
                compres_stats_list.append(stats)
                self._shuffle_files(
                    compress_status=cstatus,
                    img_file=fl,
                    proc_file=proc_fl,
                    compress_file=comp_fl,
                    )
        else:
            for flid, fl in enumerate(files):
                comp_fl = comp_paths[fl.name]['comp_fl']
                proc_fl = comp_paths[fl.name]['proc_fl']
                stats, cstatus = self.image_compressor.compress_image(
                    fl,
                    export_path=comp_fl,
                    fail_dir=self.failed_dir,
                    )
                compres_stats_list.append(stats)
                self._shuffle_files(
                    compress_status=cstatus,
                    img_file=fl,
                    proc_file=proc_fl,
                    compress_file=comp_fl,
                    )
        if len(compres_stats_list) > 0:
            compress_stats = pd.concat(compres_stats_list, ignore_index=True)
        else:
            compress_stats = []

        return compress_stats

    def _shuffle_files(self, compress_status, img_file, proc_file, compress_file):
        """shuffle around the files as needed. If image was compressed and not overwriting,
        then move the original file to the processed directory. If image was not compressed,
        then move the original file to the compressed directory"""

        if compress_status == _compressed:
            if self.overwrite is True:
                img_file.unlink()
                shutil.copy(compress_file, img_file)
            else:
                shutil.move(img_file, proc_file)
        elif compress_status == _not_compressed:
            if self.overwrite is False:
                shutil.move(img_file, compress_file)
        elif compress_status == _failed:
            pass
        else:
            self.logger.error(f"Unknown compress_status: {compress_status}")

    def _compress_files_subdir(self, subdir, progress_bar=True):
        """
        iterate through all subdirectories and compress the images. This will recursively call
        itself to iterate through all subdirectories
        """
        self.logger.info(f"Checking for files/subdirs in {subdir}")
        files, sub_directories = get_files_to_compress_recursive(
            subdir,
            img_suffixes=self.img_suffixes,
        )
        compress_stats = []
        if len(files) > 0:
            self.logger.info(f"Compressing {len(files)} files in {subdir}")
            cs = self._compress_singlesubdir_images(files, subdir, progress_bar)
            compress_stats.append(cs)
        if len(sub_directories) > 0:
            for sub_dir in sub_directories:
                cs = self._compress_files_subdir(sub_dir, progress_bar=progress_bar)
                compress_stats.append(cs)
        if len(compress_stats) > 0:
            compress_stats = pd.concat(compress_stats, ignore_index=True)
            if self.stats_fl is not False:
                compress_stats.to_csv(self.stats_fl, index=False)
        else:
            compress_stats = pd.DataFrame()
        return compress_stats

    def compress_files(self, progress_bar=True):
        """
        Compress all images in the starting directory.

        Parameters
        ----------
        subdir_file_dict : dict
            dictionary of subdirectories and files to compress. This is the output of
            get_files_to_compress
        starting_dir : str
            directory where the files are located
        compress_dir : str, optional
            directory where the compressed files will be saved. The default is 'compressed'.
        processed_dir : str, optional
            directory where the processed files will be saved. The default is 'processed'.
        img_suffixes : list, optional
            list of image suffixes to search for. The default is ['.jpg', 'jpeg', '.png'].
            any file that doesn't match these suffixes will be ignored.
        """

        compress_stats = self._compress_files_subdir(self.starting_dir, progress_bar=progress_bar)
        if self.stats_fl is not False:
            compress_stats.to_csv(self.stats_fl, index=False)

        return compress_stats


class ImageCompress(ClassWithLogger):
    def __init__(self, new_size_ratio='auto', quality='auto', to_jpg=True, n_attemps=3,
                 log_file=False, external_logger=False):
        """Compression class that given an image path, it will compress the image to try to
        save space. It will return a dataframe with the results of the compression.

        Parameters
        ----------
        new_size_ratio : float, optional
            ratio to resize the image. The default is 'auto'.
        quality : int, optional
            quality of the image. The default is 'auto'.
        to_jpg : bool, optional
            if True, then it will export the image as a jpg. The default is True.
        n_attemps : int, optional
            number of attempts to compress the image. The default is 3.
        log_file : str, optional
            path to the log file. The default is False.
        """
        super().__init__(name='ImageCompress', log_file=log_file, logger=external_logger)
        self.new_size_ratio = new_size_ratio
        self.quality = quality
        self.to_jpg = to_jpg
        self.n_attemps = n_attemps

        # 195.31KB, i.e. don't compress if image size is less than this
        self.min_compress_size = 200000

    def get_new_width_height(self, image_w, image_h, size_ratio=False):
        """
        Determine a new width and height based on new_size_ratio
        if new_size_ratio is 'auto' then it will determine the new_size_ratio based on the
        image size.

        Parameters
        ----------
        image_w : int
            image width
        image_h : int
            image height
        """
        if size_ratio is False:
            size_ratio = self.new_size_ratio

        if size_ratio == 'auto':
            if image_h > 1200:
                if image_h > 3000 or image_w > 3000:
                    size_ratio = 0.5
                else:
                    size_ratio = 0.7
            else:
                size_ratio = 1

        if size_ratio < 1.0:
            # if resizing ratio is below 1.0, then multiply width & height with this ratio
            # to reduce image size
            new_w = int(image_w * size_ratio)
            new_h = int(image_h * size_ratio)
        else:
            new_w = False
            new_h = False
        return new_w, new_h, size_ratio

    def get_quality(self, image_size):
        """
        Determine export quality based on image filesize

        Parameters
        ----------
        quality : int (0 to 100)
            quality to export image
        image_size : int
            image filesize
        """
        # determine quality
        if self.quality == 'auto':
            if image_size > 1100000:  # 1.05MB
                if image_size > 10000000:  # 9.54MB
                    quality = 70
                else:
                    quality = 80
            else:
                quality = 90
        else:
            quality = self.quality
        return quality

    def _compress_save(self, img, width, height, quality, exp_fl):
        """
        Given the width, height, and quality. Re-size and export an image to the
        exp_fl path then returns the size of the newly compressed image

        Parameters
        ----------
        image
            pillow loaded image object
        width
            new width. if False then it won't try to resize
        height
            new_height. if False then it won't try to resize
        quality
            export quality
        exp_fl
            export filename path

        Returns
        -------
            new image file size
        """
        if self.logger is not False:
            self.logger.info(f"Compressing image to {exp_fl}: width={width}, height={height}, "
                             f"quality={quality}")
        if width is False or height is False:
            compress_img = img
        else:
            try:
                compress_img = img.resize((width, height), Image.LANCZOS)
            except OSError:
                self.logger.warning(f"Failed to resize image to {width}x{height}. OSError")
                return False
        try:
            # save the image with the corresponding quality and optimize set to True
            compress_img.save(exp_fl, quality=quality, optimize=True)
        except OSError:
            try:
                if self.logger is not False:
                    self.logger.warning(f"Failed to save image to {exp_fl}. OSError, Try RGB mode")
                # convert the image to RGB mode first
                compress_img = img.convert("RGB")
                # save the image with the corresponding quality and optimize set to True
                compress_img.save(exp_fl, quality=quality, optimize=True)
            except OSError:
                if self.logger is not False:
                    self.logger.warning(f"Failed to save image to {exp_fl}. OSError")
                return False
        return exp_fl.stat().st_size

    def _check_image_corruption(self, image_path):
        """
        Check if the image is corrupted

        Parameters
        ----------
        image_path : str
            path to the image file
        """
        failed = False
        try:
            with Image.open(image_path) as img:
                img.verify()
        except (IOError, SyntaxError):
            failed = True
            if self.logger is not False:
                self.logger.error("Failed to compress due to IOError or SyntaxError")
        try:
            with Image.open(image_path) as img:
                img.load()
        except OSError as e:
            if self.logger is not False:
                self.logger.error(f"Failed to compress due to OSError: {e}")
            failed = True
        except UnidentifiedImageError:
            if self.logger is not False:
                self.logger.error("Failed to compress due to UnidentifiedImageError")
            failed = True
        except Exception as e:
            if self.logger is not False:
                self.logger.error(f"Failed to compress due to {e}")
            failed = True
        return failed

    def compress_image(self, image_path, export_path=False, fail_dir=False):
        """Compression function that given an image path, it will compress the image to try to
        save space. It will return a dataframe with the results of the compression.

        Parameters
        ----------
        image_path : str
            path to the image file
        export_path : str, optional
            path to export the compressed image. The default is False.
        fail_dir : str, optional
            if the image fails to compress, then it will move the image to this directory. if False
            then it won't move the image. The default is False.

        Returns
        -------
        results : pandas dataframe
            dataframe with the results of the compression
        status : str
            status of the compression. 'Compressed', 'NOT Compressed', or 'Failed'
        """
        if self.logger is not False:
            self.logger.info(f"Compressing {image_path}")
        status = 'Not Started'
        if self.to_jpg:
            if export_path is False:
                export_path = image_path.with_suffix('.jpg')
            else:
                export_path = export_path.with_suffix('.jpg')
        if export_path is False:
            export_path = image_path

        if self._check_image_corruption(image_path) is True:
            results = pd.DataFrame(
                {
                    'Image': [image_path],
                    'Image_size': ['-'],
                    'Status': [_failed],
                    'New_size': ['-'],
                    'Compress %': ['-'],
                    'Attempts': [0],
                }
                )
            if fail_dir is not False:
                fail_path = Path(fail_dir).joinpath(image_path.name)
                if fail_path.parent.is_dir() is False:
                    fail_path.parent.mkdir(parents=True)
                shutil.move(image_path, fail_path)
            return results, _failed

        # Force compress if we are forcing jpg and the image is not a jpg
        if self.to_jpg and image_path.suffix.lower() not in ['.jpg', '.jpeg']:
            force_compress = True
        else:
            force_compress = False
        # load the image to memory
        try:
            with Image.open(image_path) as img:

                # Get stats
                image_size = image_path.stat().st_size
                image_w, image_h = img.size

                # Determine if you need a new size
                new_w, new_h, size_ratio = self.get_new_width_height(
                    image_w,
                    image_h,
                    size_ratio=False,
                    )
                # determine quality
                quality = self.get_quality(image_size)


                compress = True
                attempts = 0
                if image_size < self.min_compress_size and force_compress is False:
                    min_size_str = get_size_format(self.min_compress_size)
                    # Don't try to compress if it's under '195.31KB'
                    if self.logger is not False:
                        self.logger.info(f"Image size is less than {min_size_str}. "
                                         "Not compressing")
                    status = _not_compressed
                    compress = False
                    new_image_size = image_size
                    shutil.copy(image_path, export_path)
                while compress is True and attempts < 3:
                    attempts += 1
                    new_image_size = self._compress_save(
                        img,
                        new_w,
                        new_h,
                        quality,
                        export_path,
                        )
                    status = _compressed
                    if new_image_size is False:
                        # if the image can't be resized then don't try to compress it
                        status = _failed
                        compress = False
                        new_image_size = image_size
                    elif new_image_size > 5000000:  # '4.77MB'
                        size_ratio -= 10
                        new_w, new_h, size_ratio = self.get_new_width_height(
                            image_w,
                            image_h,
                            size_ratio=size_ratio,
                            )
                        quality -= 10
                    elif new_image_size > 2000000:  # '1.91MB'
                        quality -= 10
                    else:
                        compress = False
                # Calculate Saving Diff
                if new_image_size == image_size:
                    saving_diff_str = '-'
                elif new_image_size > image_size:
                    if self.logger is not False:
                        self.logger.warning("New image size is greater than original image "
                                            "size. Not compressing")
                    saving_diff_str = '-'
                    shutil.copy(image_path, export_path)

                else:
                    saving_diff = (image_size - new_image_size)/image_size
                    saving_diff_str = f"{saving_diff:.1%}"
                results = pd.DataFrame(
                    {
                        'Image': [image_path],
                        'Image_size': [get_size_format(image_size)],
                        'Status': [status],
                        'New_size': [get_size_format(new_image_size)],
                        'Compress %': [saving_diff_str],
                        'Attempts': [attempts],
                    }
                    )
        except UnidentifiedImageError:
            if self.logger is not False:
                self.logger.error("Failed to compress due to UnidentifiedImageError")
            results = pd.DataFrame(
                {
                    'Image': [image_path],
                    'Image_size': ['-'],
                    'Status': [_failed],
                    'New_size': ['-'],
                    'Compress %': ['-'],
                    'Attempts': [0],
                }
                )
        return results, status
