from .utils.video_utils import _get_video_codec
from .utils.utils import get_date_12hr_min
from .utils.file_utils import get_size_format, rename_dir
from tqdm.notebook import tqdm
import ffmpeg
from pathlib import Path
from warnings import warn
import logging
import shutil
import pandas as pd

_video_suffixes = ['.mp4', '.m4v', '.mpg', '.mpeg', '.avi', '.mkv', '.mov', '.wmv', '.mts', '.ts']

_s = ' '
_s2 = 2*_s
_s4 = 4*_s


def _get_files_to_compress_recursive(main_dir, fl_suffixes='default'):
    """
    get list of files to compress from a directory, also get all subdirectories
    that can then be used to iterate through all subdirectories

    Parameters
    ----------
    main_dir : str
        directory to search for files
    fl_suffixes : list, optional
        list of suffixes to search for. The default is ['.mp4', '.m4v', '.mpg'].

    Returns
    -------
    files: list
        list of files
    sub_directories: list
        list of subdirectories
    """
    if fl_suffixes == 'default':
        fl_suffixes = _video_suffixes
    sub_directories = [folder for folder in Path(main_dir).glob('*') if folder.is_dir()]
    files = []
    files = [fl for fl in main_dir.glob('*') if fl.is_file()]
    files = [fl for fl in files if fl.suffix.lower() in fl_suffixes]

    return files, sub_directories


class MultiVideoCompress:
    def __init__(self, stats_fl='compression_stats.csv', log_file='log.txt'):
        """Compress all videos in a directory and save them to a new directory

        Parameters
        ----------
        stats_fl : str, optional
            path to csv file to save compression stats, by default 'compression_stats.csv'
        log_file : str, optional
            path to log file, by default 'log.txt'

        """

        self.stats_fl = stats_fl

        if log_file is False or log_file is None:
            self.logger = False
            self.log_file = False
        else:
            self.log_file = Path(log_file)
            if self.log_file.is_file():
                self.log_file.unlink()

            self.logger = logging.getLogger('MultiVideoCompress')
            self.logger.setLevel(logging.INFO)

        self._compress_stats_list = []
        self.compress_stats = None
        self.total_files = 0
        self.total_file_size_bytes = 0
        self.total_conv_fl_size_bytes = 0

    def _add_log_handler(self, log_file):
        """Add the log file handler to the logger"""
        # setup a file logger format so that it formats the messages to include log level,
        # class name, function name, and function arguments
        self.logger.info(f"Adding log handler for {log_file}")
        formatter = logging.Formatter('%(levelname)s: %(name)s: %(funcName)s: %(message)s')

        self._remove_log_handler(log_file)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _remove_log_handler(self, log_file):
        """Remove the log file handler from the logger"""
        self.logger.info(f"Removing log handler for {log_file}")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            if str(log_file) in handler.baseFilename:
                handler.close()
                self.logger.removeHandler(handler)

    def close_logger(self):
        """Close all handlers in the logger"""
        self.logger.info("Closing logger")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    def _get_compress_paths(self, files):
        """
        get list of image files to compress from a directory. This will iterate through all
        subdirectories

        Parameters
        ----------
        files : list
            list of files to compress

        """
        if self.logger is not False:
            self.logger.info(f"Getting compress paths for {len(files)} files")
        fl_compress_dict = {}
        for fl in files:
            comp_fl = rename_dir(fl,
                                 self.starting_dir,
                                 self.compress_dir)
            proc_fl = rename_dir(fl,
                                 self.starting_dir,
                                 self.processed_dir)
            proc_dir = proc_fl.parent
            if comp_fl.parent.is_dir() is False:
                comp_fl.parent.mkdir(parents=True)
            if proc_fl.parent.is_dir() is False:
                proc_fl.parent.mkdir(parents=True)

            fl_compress_dict[fl.name] = {'fl': fl,
                                         'comp_fl': comp_fl,
                                         'proc_fl': proc_fl,
                                         'proc_dir': proc_dir}
        return fl_compress_dict

    def _get_stats(self):
        """Get the stats from the VideoCompress object

        Parameters
        ----------
        vc : VideoCompress
            VideoCompress object

        Returns
        -------
        stats : dict
            dictionary of stats
        """
        if self.logger is not False:
            self.logger.info(f"Getting Stats for {self.video_compress.video_in.name}")

        fl_parts = self.video_compress.video_in.parts
        if len(fl_parts) > 1:
            folder = fl_parts[-2]
        else:
            folder = 'root'
        stats = {'folder': folder,
                 'video_in': self.video_compress.video_in.name,
                 'video_out': self.video_compress.video_out.name,
                 'video_height': self.video_compress.video_height_in,
                 'video_out_height': self.video_compress.video_height_out,
                 'in_file_size': get_size_format(self.video_compress.meta['file_size']),
                 'converted_fl_size': self.video_compress.conv_fl_size,
                 'compression_ratio': self.video_compress.compression_ratio}

        stats = pd.DataFrame(stats, index=[0])

        if self.video_compress.converted is True:
            self.total_files += 1
            self.total_file_size_bytes += self.video_compress.meta['file_size']
            self.total_conv_fl_size_bytes += self.video_compress.conv_fl_size_bytes
        return stats

    def _compress_singlesubdir(self, files, folder_name, progress_bar=True, change_resolution=True,
                               keep_larger_video=False, change_bitrate=True):
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
        change_resolution : bool, optional
            change the resolution of the video. If True will downgrade from 1080p to 720p, etc
            stopping at 480p
        keep_larger_video : bool, optional
            keep the larger video, by default False
        change_bitrate : bool, optional
            change the bitrate of the video to try to compress it, by default True
        """
        if self.logger is not False:
            self.logger.info((f"Compressing {len(files)} files in {folder_name}. "
                              f"progress_bar={progress_bar}"))

        comp_paths = self._get_compress_paths(files)

        if progress_bar:
            for flid, fl in enumerate(tqdm(files, desc=f'{folder_name}: ')):
                self.video_convert(video_in=comp_paths[fl.name]['fl'],
                                   video_out=comp_paths[fl.name]['comp_fl'],
                                   proc_dir=comp_paths[fl.name]['proc_dir'],
                                   change_resolution=change_resolution,
                                   keep_larger_video=keep_larger_video,
                                   change_bitrate=change_bitrate)
                stats = self._get_stats()
                self._compress_stats_list.append(stats)

        else:
            for flid, fl in enumerate(files):
                self.video_convert(video_in=comp_paths[fl.name]['fl'],
                                   video_out=comp_paths[fl.name]['comp_fl'],
                                   proc_dir=comp_paths[fl.name]['proc_dir'],
                                   change_resolution=change_resolution,
                                   keep_larger_video=keep_larger_video,
                                   change_bitrate=change_bitrate)
                stats = self._get_stats()
                self._compress_stats_list.append(stats)
        if len(self._compress_stats_list) > 0:
            self.compress_stats = pd.concat(self._compress_stats_list, ignore_index=True)
            if self.stats_fl is not False:
                self.compress_stats.to_csv(self.stats_fl,
                                           index=False)

    def _compress_files_subdir(self, subdir, progress_bar=True, change_resolution=True,
                               keep_larger_video=False, change_bitrate=True):
        """
        iterate through all subdirectories and compress the files. This will recursively call
        itself to iterate through all subdirectories

        Parameters
        ----------
        subdir : Path
            path to the subdirectory
        progress_bar : bool, optional
            if True, then it will show a progress bar for each subdirectory. The default is True.
        change_resolution : bool, optional
            change the resolution of the video. If True will downgrade from 1080p to 720p, etc
            stopping at 480p
        keep_larger_video : bool, optional
            keep the larger video, by default False
        change_bitrate : bool, optional
            change the bitrate of the video to try to compress it, by default True
        """
        if self.logger is not False:
            self.logger.info(f"Checking for files/subdirs in {subdir}")

        files, sub_directories = _get_files_to_compress_recursive(subdir)

        if len(files) > 0:
            self._compress_singlesubdir(files,
                                        subdir,
                                        progress_bar,
                                        change_resolution=change_resolution,
                                        keep_larger_video=keep_larger_video,
                                        change_bitrate=change_bitrate)

        if len(sub_directories) > 0:
            for sub_dir in sub_directories:
                self._compress_files_subdir(sub_dir,
                                            progress_bar=progress_bar,
                                            change_resolution=change_resolution,
                                            keep_larger_video=keep_larger_video,
                                            change_bitrate=change_bitrate)

    def set_dir(self, starting_dir, compress_dir='compressed', processed_dir='processed'):
        """
        Set the directories for the compression

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
        if self.logger is not False:
            self.logger.info(f"starting_dir: {self.starting_dir}")
            self.logger.info(f"compress_dir: {self.compress_dir}")
            self.logger.info(f"processed_dir: {self.processed_dir}")

    def video_convert(self, video_in, video_out, proc_dir, scale='auto', change_resolution=True,
                      keep_larger_video=False, change_bitrate=True):
        """Convert a video using the VideoCompress class

        Parameters
        ----------
        video_in : Path
            path to video file
        video_out : Path
            path to output video file
        scale : dict, optional
            dictionary of scale settings, by default 'auto'
        change_resolution : bool, optional
            change the resolution of the video. If True will downgrade from 1080p to 720p, etc
            stopping at 480p, by default True
        keep_larger_video : bool, optional
            keep the larger video, by default False
        change_bitrate : bool, optional
            change the bitrate of the video to try to compress it, by default True
        """
        if self.logger is not False:
            self.logger.info(f"Compressing {video_in.name} to {video_out.name}")
        self.video_compress = VideoCompress(video_in,
                                            video_out,
                                            scale=scale,
                                            external_logger=self.logger,
                                            warn_msg=False,
                                            change_resolution=change_resolution,
                                            change_bitrate=change_bitrate)

        self.video_compress.update_logic(keep_larger_video=keep_larger_video,
                                         delete_original=True,
                                         copy_original_if_not_converted=True,
                                         proccessed_folder=proc_dir)
        self.video_compress.convert_video()

    def compress_files(self, progress_bar=True, change_resolution=True, keep_larger_video=False,
                       change_bitrate=True):
        """
        Compress all videos in the starting directory.

        Parameters
        ----------
        progress_bar : bool, optional
            if True, then it will show a progress bar for each subdirectory. The default is True.
        change_resolution : bool, optional
            change the resolution of the video. If True will downgrade from 1080p to 720p, etc
            stopping at 480p
        keep_larger_video : bool, optional
            keep the larger video, by default False
        change_bitrate : bool, optional
            change the bitrate of the video to try to compress it, by default True
        """
        # add the log file handler
        if self.logger is not False:
            self._add_log_handler(log_file=self.log_file)
        self._compress_files_subdir(self.starting_dir,
                                    progress_bar=progress_bar,
                                    change_resolution=change_resolution,
                                    keep_larger_video=keep_larger_video,
                                    change_bitrate=change_bitrate)

        if self.logger is not False:
            self.logger.info(f"Total Files: {self.total_files}")
            total_file_size = get_size_format(self.total_file_size_bytes)
            self.logger.info(f"Total File Size: {total_file_size}")
            total_conv_fl_size = get_size_format(self.total_conv_fl_size_bytes)
            self.logger.info(f"Total Converted File Size: {total_conv_fl_size}")
            conversion_ratio = self.total_conv_fl_size_bytes/self.total_file_size_bytes
            self.logger.info(f"Total Conversion Ratio: {conversion_ratio:0.1%}")

            print(f"Total Files: {self.total_files}")
            print(f"Total File Size: {total_file_size}")
            print(f"Total Converted File Size: {total_conv_fl_size}")
            print(f"Total Conversion Ratio: {conversion_ratio:0.1%}")

        # close the logger
        if self.logger is not False:
            self._remove_log_handler(log_file=self.log_file)
        return True


# VideoCompress class that will compress a video using ffmpeg
class VideoCompress:
    """Compress or convert a video using ffmpeg

    Parameters
    ----------
    video_in : Path
        path to video file
    video_out : Path
        path to output video file
    scale : dict, optional
        dictionary of scale settings, by default None
    log_file : str, optional
        path to log file, by default False
    external_logger : logger, optional
        external logger, by default False
    warn_msg : bool, optional
        show warning messages, by default True
    change_resolution : bool, optional
        change the resolution of the video. If True will downgrade from 1080p to 720p, etc stopping
        at 480p, by default True
    """
    def __init__(self, video_in, video_out, scale='auto', log_file=False,
                 external_logger=False, warn_msg=True, change_resolution=True, change_bitrate=True):
        self.video_in = Path(video_in)
        self.video_out = Path(video_out)
        self._warn_msg = warn_msg
        self._log_file = log_file

        if external_logger is not False:
            self._set_external_logger(external_logger)
            self._external_logger = True
        else:
            self._external_logger = False
            self._set_logger()

        if self.video_out.suffix != '.mp4':
            if warn_msg:
                warn("VideoCompress only supports .mp4 output files."
                     " Changing output file suffix to .mp4")
            if self.logger is not False:
                self.logger.warning(f"{_s2}Changing output file suffix to .mp4")
            self.video_out = self.video_out.with_suffix('.mp4')

        self.scale = scale
        self.video_height = None
        self.change_resolution = change_resolution
        self.change_bitrate = change_bitrate

        self.codec = self._get_video_codec(self.video_in)
        self._set_video_metadata()
        self._set_output_settings()
        self._make_output_dirs()

        self.fl_size_bytes = 0
        self.conv_fl_size_bytes = 0
        self.conv_fl_size = "Not Converted"

        # Logic
        self.keep_larger_video = False
        self.delete_original = False
        self.move_original = False
        self.copy_original_if_not_converted = False

        self.converted = False

    def _set_logger(self):
        """Set the logger"""
        if self._log_file is not False:
            self.logger = logging.getLogger('ImageCompress')
            self.logger.setLevel(logging.INFO)
            self._add_log_handler(self._log_file)

    def _add_log_handler(self, log_file):
        """Add the log file handler to the logger"""
        # setup a file logger format so that it formats the messages to include log level,
        # class name, function name, and function arguments
        self.logger.info(f"Adding log handler for {log_file}")
        formatter = logging.Formatter('%(levelname)s: %(name)s: %(funcName)s: %(message)s')

        self._remove_log_handler(log_file)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _remove_log_handler(self, log_file):
        """Remove the log file handler from the logger"""
        self.logger.info(f"Removing log handler for {log_file}")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            if log_file in handler.baseFilename:
                handler.close()
                self.logger.removeHandler(handler)

    def _set_external_logger(self, logger):
        """Set an external logger"""
        self.logger = logger

    def close_logger(self):
        """Close all handlers in the logger"""
        self.logger.info("Closing logger")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    @staticmethod
    def _get_video_codec(fl):
        """ get video codec based on file extension
        """
        return _get_video_codec(fl)

    def _make_output_dirs(self):
        """check if output and proccessed directories exist, if not create them"""
        if self.video_out.parent.is_dir() is False:
            self.video_out.parent.mkdir(parents=True)

    def _set_video_metadata(self):
        """Extract video metadata from a file

        Parameters
        ----------
        fl : Path
            path to video file

        Returns
        -------
        meta : dict
            dictionary of video metadata"""

        info = ffmpeg.probe(self.video_in)
        streams = info['streams']

        meta = {}
        for strm in streams:
            if strm['codec_type'] == "video":
                meta['video'] = strm
                meta['video_codec_name'] = strm['codec_name']
            elif strm['codec_type'] == "audio":
                meta['audio'] = strm
                meta['audio_codec_name'] = strm['codec_name']
        self.fl_size_bytes = self.video_in.stat().st_size
        meta['file_size'] = self.fl_size_bytes

        self.meta = meta

    def _set_output_settings(self):
        """Set output settings for ffmpeg

        Returns
        -------
        dict
            dictionary of output settings
        """
        self.out_settings = {}

        self.out_settings['c:v'] = 'libx264'
        bitrate = '512K'

        if self.meta['audio_codec_name'] == 'aac':
            self.out_settings['c:a'] = 'copy'
        else:
            self.out_settings['c:a'] = 'aac'
            self.out_settings['b:a'] = '128K'

        video_height = self.meta['video']['height']
        self.video_height_in = video_height

        if video_height >= 1080:
            convert_to = 720
            bitrate = '1M'
        elif video_height >= 480:
            convert_to = 480
        else:
            convert_to = video_height

        if self.change_resolution is False:
            convert_to = video_height

        if self.scale == 'auto':
            self.scale = {'width': -2,
                          'height': convert_to}
        self.video_height_out = convert_to
        if self.change_bitrate is True:
            self.out_settings['b:v'] = bitrate
        if self.logger is not False:
            self.logger.info(f"Output Height: {self.video_height_out}")

    def _output_with_scale(self, video_stream, audio_stream):
        """
        Output video with scaling

        Parameters
        ----------
        video_stream : ffmpeg stream
            video stream
        audio_stream : ffmpeg stream
            audio stream
        """
        if self.logger is not False:
            self.logger.info(f"Outputting {self.video_out.name} with scaling")

        output_video_stream = video_stream.filter('scale',
                                                  **self.scale)

        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(self.video_out),
                                           **self.out_settings)
        try:
            out, err = video_audio_stream.overwrite_output().run(capture_stdout=True,
                                                                 capture_stderr=True)
            return True
        except ffmpeg.Error as err:
            if self.logger is not False:
                err_msg = 'stderr: ' + err.stderr.decode('utf8')
                self.logger.exception(err_msg)
            return False

    def _output_no_scale(self, video_stream, audio_stream):
        """
        Output video without scaling

        Parameters
        ----------
        video_stream : ffmpeg stream
            video stream
        audio_stream : ffmpeg stream
            audio stream
        """
        if self.logger is not False:
            self.logger.info(f"Outputting {self.video_out.name} without scaling")

        output_video_stream = video_stream
        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(self.video_out),
                                           **self.out_settings)
        try:
            out, err = video_audio_stream.overwrite_output().run(capture_stdout=True,
                                                                 capture_stderr=True)
            return True
        except ffmpeg.Error as err:
            if self.logger is not False:
                err_msg = 'stderr: ' + err.stderr.decode('utf8')
                self.logger.exception(err_msg)
            return False

    def update_logic(self, keep_larger_video=None, delete_original=None,
                     copy_original_if_not_converted=None, proccessed_folder=None):
        """Update the logic for the VideoCompress object

        *None values will not be updated*

        Parameters
        ----------
        keep_larger_video : bool, optional
            Keep the larger video, by default None
        delete_original : bool, optional
            Delete the original video, by default None
        copy_original_if_not_converted : bool, optional
            Copy the original video if it is not converted, by default None
        proccessed_folder : str, optional
            Move the original video to the processed folder, by default None
        """
        if keep_larger_video is not None:
            self.keep_larger_video = keep_larger_video
        if delete_original is not None:
            self.delete_original = delete_original
        if copy_original_if_not_converted is not None:
            self.copy_original_if_not_converted = copy_original_if_not_converted

        if proccessed_folder is not None:
            self.move_original = True
            self.proccessed_folder = Path(proccessed_folder)
            if self.proccessed_folder.is_dir() is False:
                self.proccessed_folder.mkdir(parents=True)

    def _check_logic(self):
        """ Deal with the video files after compression based on class logic"""
        if self.logger is not False:
            self.logger.info(f"Checking logic for {self.video_out.name}")

        if self.keep_larger_video is False:
            if self.video_out.stat().st_size > self.meta['file_size']:
                if self._warn_msg:
                    warn("Converted file size is larger than original file size:"
                         f" {self.video_out.name}")
                self.video_out.unlink()
                if self.copy_original_if_not_converted:
                    if self.video_in.suffix != self.video_out.suffix:
                        self.video_out = self.video_out.with_suffix(self.video_in.suffix)

                    if self.move_original is True or self.delete_original is False:
                        shutil.copy2(self.video_in, self.video_out)
                    else:
                        self.video_in.rename(self.video_out)

        if self.move_original:
            if self.delete_original:
                self.video_in.rename(self.proccessed_folder.joinpath(self.video_in.name))
            else:
                shutil.copy2(self.video_in, self.proccessed_folder.joinpath(self.video_in.name))

        if self.delete_original:
            if self.video_in.is_file():
                self.video_in.unlink()

    def convert_video(self):
        """
        Convert videos using ffmpeg

        """
        date_time = get_date_12hr_min()
        if self.logger is not False:
            self.logger.info(f'Started Conversion: {date_time}')

        self.converted = False

        video_stream = ffmpeg.input(str(self.video_in)).video
        audio_stream = ffmpeg.input(str(self.video_in)).audio

        if self.video_height_out == 480:
            self.converted = self._output_no_scale(video_stream,
                                                   audio_stream)
        if not self.converted:
            self.converted = self._output_with_scale(video_stream,
                                                     audio_stream)
        if self.converted:
            self._check_logic()
            conv_fl_size = self.video_out.stat().st_size
            self.conv_fl_size_bytes = conv_fl_size
            conv_dif = conv_fl_size/self.meta['file_size']

            if self.logger is not False:
                self.logger.info(f"Conversion Completed at {conv_dif:0.1%}: {self.video_out.name}")
            self.conv_fl_size = get_size_format(conv_fl_size)
            self.compression_ratio = f"{conv_dif:0.1%}"

        else:
            self.conv_fl_size = "Not Converted"
            self.compression_ratio = "NA"
            if self.logger is not False:
                self.logger.info(f"Conversion Failed: {self.video_out.name}")
            if self._warn_msg:
                warn(f"Conversion Failed: {self.video_out.name}")
        if self.logger is not False and self._external_logger is False:
            self.close_logger()
