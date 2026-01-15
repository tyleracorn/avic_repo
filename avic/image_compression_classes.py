from PIL import Image
from pathlib import Path
import pandas as pd
from .utils.file_utils import get_size_format, get_target_path
from tqdm.notebook import tqdm
import shutil
from PIL import UnidentifiedImageError
from .utils.logger import ClassWithLogger
from enum import Enum


class CompressionStatus(Enum):
    FAILED = 'Failed'
    COMPRESSED = 'Compressed'
    NOT_COMPRESSED = 'NOT Compressed'


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
            comp_fl = get_target_path(fl, starting_dir, compress_dir)
            proc_fl = get_target_path(fl, starting_dir, processed_dir)
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


class CompressionFileManager:
    """Handles all file path and directory operations for compression workflow"""

    def __init__(self, starting_dir, compress_dir, processed_dir, failed_dir, overwrite):
        """
        Initialize the file manager with directory paths.

        Parameters
        ----------
        starting_dir : str or Path
            Base directory containing source images
        compress_dir : str or Path
            Directory where compressed images will be saved
        processed_dir : str or Path
            Directory where successfully processed originals will be moved
        failed_dir : str or Path
            Directory where failed images will be moved
        overwrite : bool
            If True, replace original files with compressed versions
        """
        self.starting_dir = Path(starting_dir)
        self.compress_dir = Path(compress_dir)
        self.processed_dir = Path(processed_dir)
        self.failed_dir = Path(failed_dir)
        self.overwrite = overwrite

    def get_compression_paths(self, source_file):
        """
        Get all relevant file paths for compression workflow.

        Parameters
        ----------
        source_file : Path
            Source image file path

        Returns
        -------
        dict
            Dictionary with keys: 'comp_fl', 'proc_fl', 'fail_fl'
            proc_fl will be False if overwrite=True
        """
        fail_fl = get_target_path(source_file, self.starting_dir, self.failed_dir)

        if self.overwrite:
            # When overwriting, compress in place and don't need processed path
            comp_fl = source_file
            proc_fl = False
        else:
            comp_fl = get_target_path(source_file, self.starting_dir, self.compress_dir)
            proc_fl = get_target_path(source_file, self.starting_dir, self.processed_dir)

            # Ensure parent directories exist
            comp_fl.parent.mkdir(parents=True, exist_ok=True)
            proc_fl.parent.mkdir(parents=True, exist_ok=True)

        # Ensure fail directory exists
        fail_fl.parent.mkdir(parents=True, exist_ok=True)

        return {
            'comp_fl': comp_fl,
            'proc_fl': proc_fl,
            'fail_fl': fail_fl,
        }

    def handle_compression_result(self, status, img_file, proc_file, compress_file):
        """
        Move files to appropriate locations based on compression result.

        Logic:
        - Compressed/Not Compressed + overwrite: Replace original with processed version
        - Compressed/Not Compressed + no overwrite: Move original to processed directory
        - Failed: Do nothing (already handled by compress_image)

        Note: NOT_COMPRESSED is treated the same as COMPRESSED for file operations.
        The file in compress_file is either a newly compressed image or a copy of
        the original (if it was too small to compress).

        Parameters
        ----------
        status : str
            Compression status value
        img_file : Path
            Original image file path
        proc_file : Path or False
            Path to move processed original to (False if overwrite=True)
        compress_file : Path
            Path where compressed/copied image is located
        """
        if status in (CompressionStatus.COMPRESSED.value, CompressionStatus.NOT_COMPRESSED.value):
            if self.overwrite:
                # Replace original with the file in compress location
                shutil.move(compress_file, img_file)
            else:
                # Keep compressed/copied file, move original to processed
                shutil.move(img_file, proc_file)

        elif status == CompressionStatus.FAILED.value:
            # Already handled in compress_image
            pass
        else:
            raise ValueError(f"Unknown compression status: {status}")


class MultiImageCompression(ClassWithLogger):
    def __init__(self,
                 img_suffixes=['.jpg', 'jpeg', '.png'], stats_fl='compression_stats.csv',
                 to_jpg=True, overwrite=False, log_file='log.txt', external_logger=False):
        """
        Compress all images in a directory and save them to a new directory.

        Parameters
        ----------
        img_suffixes : list, optional
            list of image suffixes to search for. The default is ['.jpg', 'jpeg', '.png'].
            any file that doesn't match these suffixes will be ignored.
        stats_fl : str, optional
            path to save compression statistics CSV. The default is 'compression_stats.csv'.
        to_jpg : bool, optional
            if True, convert images to JPG format. The default is True.
        overwrite : bool, optional
            if True, overwrite original files with compressed versions. The default is False.
        log_file : str, optional
            path to log file. The default is 'log.txt'.
        external_logger : bool or logger, optional
            external logger instance. The default is False.

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
        self.file_manager = None
        self.img_suffixes = img_suffixes
        self.stats_fl = stats_fl
        self.to_jpg = to_jpg
        self.overwrite = overwrite

        self.image_compressor = ImageCompress(new_size_ratio='auto',
                                              quality='auto',
                                              to_jpg=self.to_jpg,
                                              n_attempts=3,
                                              log_file=False,
                                              external_logger=self.logger)

    def set_dir(self, starting_dir, compress_dir='compressed', processed_dir='processed',
                failed_dir='failed'):
        """
        Set the directories for the image compression.

        The directory structure will be preserved from starting_dir when creating
        files in compress_dir, processed_dir, and failed_dir.

        Parameters
        ----------
        starting_dir : str or Path
            directory where the source files are located
        compress_dir : str or Path, optional
            directory where the compressed files will be saved. The default is 'compressed'.
        processed_dir : str or Path, optional
            directory where the successfully processed original files will be moved.
            The default is 'processed'.
        failed_dir : str or Path, optional
            directory where failed files will be moved. The default is 'failed'.
        """
        self.file_manager = CompressionFileManager(
            starting_dir=starting_dir,
            compress_dir=compress_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            overwrite=self.overwrite
        )
        self.log_info(f"starting_dir: {self.file_manager.starting_dir}")
        self.log_info(f"compress_dir: {self.file_manager.compress_dir}")
        self.log_info(f"processed_dir: {self.file_manager.processed_dir}")

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
        self.log_info((f"Compressing {len(files)} files in {folder_name}. "
                       f"progress_bar={progress_bar}"))
        compres_stats_list = []

        if progress_bar:
            for fl in tqdm(files, desc=f'{folder_name}: '):
                paths = self.file_manager.get_compression_paths(fl)
                stats, cstatus = self.image_compressor.compress_image(
                    fl,
                    export_path=paths['comp_fl'],
                    fail_dir=paths['fail_fl'].parent,
                )
                compres_stats_list.append(stats)
                self.file_manager.handle_compression_result(
                    status=cstatus,
                    img_file=fl,
                    proc_file=paths['proc_fl'],
                    compress_file=paths['comp_fl'],
                )
        else:
            for fl in files:
                paths = self.file_manager.get_compression_paths(fl)
                stats, cstatus = self.image_compressor.compress_image(
                    fl,
                    export_path=paths['comp_fl'],
                    fail_dir=paths['fail_fl'].parent,
                )
                compres_stats_list.append(stats)
                self.file_manager.handle_compression_result(
                    status=cstatus,
                    img_file=fl,
                    proc_file=paths['proc_fl'],
                    compress_file=paths['comp_fl'],
                )

        if len(compres_stats_list) > 0:
            compress_stats = pd.concat(compres_stats_list, ignore_index=True)
        else:
            compress_stats = []

        return compress_stats

    def _compress_files_subdir(self, subdir, progress_bar=True):
        """
        iterate through all subdirectories and compress the images. This will recursively call
        itself to iterate through all subdirectories
        """
        self.log_info(f"Checking for files/subdirs in {subdir}")
        files, sub_directories = get_files_to_compress_recursive(
            subdir,
            img_suffixes=self.img_suffixes,
        )
        compress_stats = []
        if len(files) > 0:
            self.log_info(f"Compressing {len(files)} files in {subdir}")
            cs = self._compress_singlesubdir_images(files, subdir, progress_bar)
            compress_stats.append(cs)
        if len(sub_directories) > 0:
            for sub_dir in sub_directories:
                cs = self._compress_files_subdir(sub_dir, progress_bar=progress_bar)
                compress_stats.append(cs)
        if len(compress_stats) > 0:
            compress_stats = pd.concat(compress_stats, ignore_index=True)
            if self.stats_fl is not False:
                # Append to CSV (header only if file doesn't exist yet)
                mode = 'a' if Path(self.stats_fl).exists() else 'w'
                header = not Path(self.stats_fl).exists()
                compress_stats.to_csv(self.stats_fl, mode=mode, header=header, index=False)
        else:
            compress_stats = pd.DataFrame()
        return compress_stats

    def _parse_size_string(self, size_str):
        """
        Parse size strings like '1.5MB', '500KB' back to bytes.
        Returns 0 if unable to parse (e.g., '-' for failed images).

        Parameters
        ----------
        size_str : str
            Size string in format like '1.5MB', '500KB', '1.2GB'

        Returns
        -------
        int
            Size in bytes
        """
        if size_str == '-' or pd.isna(size_str):
            return 0

        size_str = str(size_str).strip().upper()

        # Extract number and unit
        import re
        match = re.match(r'([\d.]+)\s*([KMGT]?B)', size_str)
        if not match:
            return 0

        number = float(match.group(1))
        unit = match.group(2)

        # Convert to bytes
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4,
        }

        return int(number * multipliers.get(unit, 1))

    def _print_compression_summary(self, stats_df):
        """
        Print a summary of compression results.

        Parameters
        ----------
        stats_df : pandas.DataFrame
            DataFrame containing compression statistics
        """
        if len(stats_df) == 0:
            self.log_info("No files were processed")
            print("\n" + "="*60)
            print("COMPRESSION SUMMARY")
            print("="*60)
            print("No files were processed")
            print("="*60 + "\n")
            return

        # Count statuses
        total_files = len(stats_df)
        compressed = len(stats_df[stats_df['Status'] == CompressionStatus.COMPRESSED.value])
        not_compressed = len(stats_df[stats_df['Status'] == CompressionStatus.NOT_COMPRESSED.value])
        failed = len(stats_df[stats_df['Status'] == CompressionStatus.FAILED.value])

        # Calculate sizes (exclude failed images)
        successful = stats_df[stats_df['Status'] != CompressionStatus.FAILED.value].copy()

        if len(successful) > 0:
            # Parse size strings back to bytes
            successful['orig_bytes'] = successful['Image_size'].apply(self._parse_size_string)
            successful['new_bytes'] = successful['New_size'].apply(self._parse_size_string)

            total_original_bytes = successful['orig_bytes'].sum()
            total_new_bytes = successful['new_bytes'].sum()
            total_saved_bytes = total_original_bytes - total_new_bytes

            if total_original_bytes > 0:
                percent_saved = (total_saved_bytes / total_original_bytes) * 100
            else:
                percent_saved = 0

            # Format sizes for display
            total_original = get_size_format(total_original_bytes)
            total_new = get_size_format(total_new_bytes)
            total_saved = get_size_format(total_saved_bytes)
        else:
            total_original = "0B"
            total_new = "0B"
            total_saved = "0B"
            percent_saved = 0

        # Print summary
        print("\n" + "="*60)
        print("COMPRESSION SUMMARY")
        print("="*60)
        print(f"Total files processed:     {total_files}")
        print(f"  - Compressed:            {compressed}")
        print(f"  - Not compressed:        {not_compressed}")
        print(f"  - Failed:                {failed}")
        print("-"*60)
        print(f"Total original size:       {total_original}")
        print(f"Total compressed size:     {total_new}")
        print(f"Total space saved:         {total_saved} ({percent_saved:.1f}%)")
        print("="*60 + "\n")

        self.log_info(f"Compression complete: {compressed} compressed, {not_compressed} skipped, "
                      f"{failed} failed. Saved {total_saved} ({percent_saved:.1f}%)")

    def compress_files(self, progress_bar=True):
        """
        Compress all images in the starting directory.

        Parameters
        ----------
        progress_bar : bool, optional
            if True, show progress bars during compression. The default is True.

        Returns
        -------
        pandas.DataFrame
            DataFrame containing compression statistics for all processed files
        """
        if self.file_manager is None:
            raise ValueError("Must call set_dir() before compress_files()")

        # Delete existing stats file to start fresh
        if self.stats_fl is not False and Path(self.stats_fl).exists():
            Path(self.stats_fl).unlink()
            self.log_info(f"Deleted existing stats file: {self.stats_fl}")

        # Compress all files
        self.compress_stats = self._compress_files_subdir(
            self.file_manager.starting_dir,
            progress_bar=progress_bar
        )

        self._print_compression_summary(self.compress_stats)

        return self.compress_stats


class ImageCompress(ClassWithLogger):
    def __init__(self, new_size_ratio='auto', quality='auto', to_jpg=True, n_attempts=3,
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
        n_attempts : int, optional
            number of attempts to compress the image. The default is 3.
        log_file : str, optional
            path to the log file. The default is False.
        """
        super().__init__(name='ImageCompress', log_file=log_file, logger=external_logger)
        self.new_size_ratio = new_size_ratio
        self.quality = quality
        self.to_jpg = to_jpg
        self.n_attempts = n_attempts

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
        if image_h < 0:
            image_h *= -1
        if image_w < 0:
            image_w *= -1
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
        self.log_info(f"Compressing image to {exp_fl}: width={width}, height={height}, "
                      f"quality={quality}")
        if width is False or height is False:
            compress_img = img
        else:
            try:
                compress_img = img.resize((width, height), Image.LANCZOS)
            except OSError:
                self.log_warning(f"Failed to resize image to {width}x{height}. OSError")
                return False
        try:
            # save the image with the corresponding quality and optimize set to True
            compress_img.save(exp_fl, quality=quality, optimize=True)
        except OSError:
            try:
                self.log_warning(f"Failed to save image to {exp_fl}. OSError, Try RGB mode")
                # convert the image to RGB mode first
                compress_img = compress_img.convert("RGB")
                # save the image with the corresponding quality and optimize set to True
                compress_img.save(exp_fl, quality=quality, optimize=True)
            except OSError:
                self.log_warning(f"Failed to save image to {exp_fl}. OSError")
                return False
            except Exception as e:
                self.log_warning(f"Failed to save image to {exp_fl}. {e}")
                return False
        except Exception as e:
            self.log_warning(f"Failed to save image to {exp_fl}. {e}")
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
            self.log_error("Failed to compress due to IOError or SyntaxError")
        try:
            with Image.open(image_path) as img:
                img.load()
        except OSError as e:
            self.log_error(f"Failed to compress due to OSError: {e}")
            failed = True
        except UnidentifiedImageError:
            self.log_error("Failed to compress due to UnidentifiedImageError")
            failed = True
        except Exception as e:
            self.log_error(f"Failed to compress due to {e}")
            failed = True
        return failed

    def _determine_export_path(self, image_path, export_path):
        """Determine the export path, converting to .jpg if needed"""
        if self.to_jpg:
            if export_path is False:
                return image_path.with_suffix('.jpg')
            else:
                return export_path.with_suffix('.jpg')
        return export_path if export_path is not False else image_path

    def _should_force_compress(self, image_path):
        """Check if we should force compression (e.g., converting to JPG)"""
        return self.to_jpg and image_path.suffix.lower() not in ['.jpg', '.jpeg']

    def _handle_failed_image(self, image_path, fail_dir):
        """Move failed image to fail directory if specified"""
        if fail_dir is not False:
            fail_path = Path(fail_dir).joinpath(image_path.name)
            if fail_path.parent.is_dir() is False:
                fail_path.parent.mkdir(parents=True)
            shutil.move(image_path, fail_path)

    def _create_failed_stats(self, image_path, attempts=0):
        """Create a DataFrame for a failed compression"""
        return pd.DataFrame({
            'Image': [image_path],
            'Image_size': ['-'],
            'Status': [CompressionStatus.FAILED.value],
            'New_size': ['-'],
            'Compress %': ['-'],
            'Attempts': [attempts],
        })

    def _create_success_stats(self, image_path, result):
        """Create a DataFrame for a successful or skipped compression"""
        image_size = result['image_size']
        new_image_size = result['new_image_size']

        # Calculate saving percentage
        if new_image_size == image_size or new_image_size > image_size:
            saving_diff_str = '-'
        else:
            saving_diff = (image_size - new_image_size) / image_size
            saving_diff_str = f"{saving_diff:.1%}"

        return pd.DataFrame({
            'Image': [image_path],
            'Image_size': [get_size_format(image_size)],
            'Status': [result['status']],
            'New_size': [get_size_format(new_image_size)],
            'Compress %': [saving_diff_str],
            'Attempts': [result['attempts']],
        })

    def _should_skip_compression(self, image_size, force_compress):
        """Check if image is too small to compress"""
        return image_size < self.min_compress_size and not force_compress

    def _attempt_compression_with_retry(self, img, image_path, export_path, force_compress):
        """
        Attempt to compress an image with retry logic.

        Returns a dict with compression results:
        {
            'status': str,
            'image_size': int,
            'new_image_size': int,
            'attempts': int
        }
        """
        # Get initial image stats
        image_size = image_path.stat().st_size
        image_w, image_h = img.size

        # Check if we should skip compression
        if self._should_skip_compression(image_size, force_compress):
            min_size_str = get_size_format(self.min_compress_size)
            self.log_info(f"Image size is less than {min_size_str}. Not compressing")
            shutil.copy(image_path, export_path)
            return {
                'status': CompressionStatus.NOT_COMPRESSED.value,
                'image_size': image_size,
                'new_image_size': image_size,
                'attempts': 0,
            }

        # Determine initial compression parameters
        new_w, new_h, size_ratio = self.get_new_width_height(image_w, image_h, size_ratio=False)
        quality = self.get_quality(image_size)

        # Attempt compression with retry logic
        attempts = 0
        while attempts < self.n_attempts:
            attempts += 1
            new_image_size = self._compress_save(img, new_w, new_h, quality, export_path)

            # Handle compression failure
            if new_image_size is False:
                self.log_warning("Failed to compress image")
                return {
                    'status': CompressionStatus.FAILED.value,
                    'image_size': image_size,
                    'new_image_size': image_size,
                    'attempts': attempts,
                }

            # Check if we need another attempt with different parameters
            if new_image_size > 5000000:  # 4.77MB
                size_ratio -= 10
                new_w, new_h, size_ratio = self.get_new_width_height(
                    image_w, image_h, size_ratio=size_ratio
                )
                quality -= 10
            elif new_image_size > 2000000:  # 1.91MB
                quality -= 10
            else:
                # Compression successful and meets size requirements
                break

        # Handle case where compressed file is larger than original
        if new_image_size > image_size:
            self.log_warning("New image size is greater than original image size. Using original")
            shutil.copy(image_path, export_path)
            return {
                'status': CompressionStatus.NOT_COMPRESSED.value,
                'image_size': image_size,
                'new_image_size': image_size,
                'attempts': attempts,
            }

        return {
            'status': CompressionStatus.COMPRESSED.value,
            'image_size': image_size,
            'new_image_size': new_image_size,
            'attempts': attempts,
        }

    def compress_image(self, image_path, export_path=False, fail_dir=False):
        """Compression function that given an image path, it will compress the image to try to
        save space. It will return a dataframe with the results of the compression.

        Parameters
        ----------
        image_path : str or Path
            path to the image file
        export_path : str or Path, optional
            path to export the compressed image. The default is False.
        fail_dir : str or Path, optional
            if the image fails to compress, then it will move the image to this directory. if False
            then it won't move the image. The default is False.

        Returns
        -------
        results : pandas.DataFrame
            dataframe with the results of the compression
        status : str
            status of the compression. 'Compressed', 'NOT Compressed', or 'Failed'
        """
        self.log_info(f"Compressing {image_path}")

        # Determine export path
        export_path = self._determine_export_path(image_path, export_path)

        # Check for corruption
        if self._check_image_corruption(image_path):
            self._handle_failed_image(image_path, fail_dir)
            return self._create_failed_stats(image_path, attempts=0), CompressionStatus.FAILED.value

        # Check if we should force compression
        force_compress = self._should_force_compress(image_path)

        # Attempt compression
        try:
            with Image.open(image_path) as img:
                result = self._attempt_compression_with_retry(
                    img, image_path, export_path, force_compress
                )
                stats = self._create_success_stats(image_path, result)
                return stats, result['status']
        except UnidentifiedImageError:
            self.log_error("Failed to compress due to UnidentifiedImageError")
            return self._create_failed_stats(image_path, attempts=0), CompressionStatus.FAILED.value