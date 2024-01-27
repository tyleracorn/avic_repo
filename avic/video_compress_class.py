from .utils.video_utils import _get_video_codec
from .utils.utils import get_date_12hr_min
from .utils.file_utils import get_size_format
import ffmpeg
from pathlib import Path
from warnings import warn
import logging
import shutil


_s = ' '
_2s = 2*_s
_4s = 4*_s


class MultiVideoCompress:
    def __init__(self, stats_fl='compression_stats.csv', overwrite=False, log_file='log.txt'):
        """Compress all videos in a directory and save them to a new directory

        Parameters
        ----------
        stats_fl : str, optional
            path to csv file to save compression stats, by default 'compression_stats.csv'
        overwrite : bool, optional
            overwrite any output files, by default False
        log_file : str, optional
            path to log file, by default 'log.txt'
        """

        self.stats_fl = stats_fl
        self.overwrite = overwrite


        if log_file is False or log_file is None:
            self.logger = False
            self.log_file = False
        else:
            self.log_file = Path(log_file)
            if self.log_file.is_file():
                self.log_file.unlink()
            self._set_logger()
            self.logger = logging.getLogger('MultiVideoCompress')
            self.logger.setLevel(logging.INFO)
        self._set_stats_df()



# VideoCompress class that will compress a video using ffmpeg
class VideoCompress:
    """Compress a video using ffmpeg

    Parameters
    ----------
    video_in : Path
        path to video file
    video_out : Path
        path to output video file
    scale : dict, optional
        dictionary of scale settings, by default None
    settings : dict, optional
        dictionary of output settings, by default None
    """
    def __init__(self, video_in, video_out, scale='auto', log_file=False, warn_msg=True):
        self.video_in = Path(video_in)
        self.video_out = Path(video_out)
        self.warn_msg = warn_msg

        if log_file is False or log_file is None:
            self.logger = False
        else:
            self._set_logger(log_file)

        if self.video_out.suffix != '.mp4':
            if warn_msg:
                warn("VideoCompress only supports .mp4 output files."
                     " Changing output file suffix to .mp4")
            self.video_out = self.video_out.with_suffix('.mp4')

        self.scale = scale
        self.video_height = None

        self.codec = self._get_video_codec(self.video_in)
        self._set_video_metadata()
        self._set_output_settings()
        self._make_output_dirs()

        # Logic
        self.keep_larger_video = False
        self.delete_original = False
        self.move_original = False
        self.copy_original_if_not_converted = False

    def _set_logger(self, log_file):
        """Set the logger"""
        self.logger = logging.getLogger('ImageCompress')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s: %(name)s: %(funcName)s: %(message)s')
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _remove_logger(self):
        """Remove the logger"""
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    def _set_external_logger(self, logger):
        """Set an external logger"""
        self.logger = logger

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
            elif strm['codec_type'] == "audio":
                meta['audio'] = strm
        meta['file_size'] = self.video_in.stat().st_size
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
        self.out_settings['b:v'] = '512K'
        self.out_settings['c:a'] = 'copy'

        video_height = self.meta['video']['height']
        if video_height >= 1080:
            convert_to = 720
            self.out_settings['b:v'] = '1M'
        elif video_height >= 480:
            convert_to = 480
        else:
            convert_to = video_height

        if self.scale == 'auto':
            self.scale = {'width': -2,
                          'height': convert_to}
        self.out_video_height = convert_to

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

        try:
            output_video_stream = video_stream.filter('scale',  **self.scale)
            video_audio_stream = ffmpeg.output(output_video_stream,
                                               audio_stream,
                                               str(self.video_out),
                                               **self.out_settings)
            video_audio_stream.overwrite_output().run()
            return True
        except:
            logging.exception("output_with_scale failed")
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

        try:
            output_video_stream = video_stream
            video_audio_stream = ffmpeg.output(output_video_stream,
                                               audio_stream,
                                               str(self.video_out),
                                               **self.out_settings)
            video_audio_stream.overwrite_output().run()
            return True
        except:
            logging.exception("output_no_scale failed")
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

        if self.keep_larger_video is False:
            if self.video_out.stat().st_size > self.meta['file_size']:
                if self.warn_msg:
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
            logging.info(f'Started Conversion: {date_time} \n')

        converted = False

        video_stream = ffmpeg.input(str(self.video_in)).video
        audio_stream = ffmpeg.input(str(self.video_in)).audio

        if self.out_video_height == 480:
            converted = self._output_no_scale(video_stream,
                                              audio_stream)
        if not converted:
            converted = self._output_with_scale(video_stream,
                                                audio_stream)
        if converted:
            self._check_logic()
            conv_fl_size = self.video_out.stat().st_size
            self.conv_fl_size = conv_fl_size
            conv_dif = conv_fl_size/self.meta['file_size']

            if self.logger is not False:
                logging.info(f"Conversion Completed at {conv_dif:0.1%}: {self.video_out.name} \n")
            self.conv_fl_size = get_size_format(conv_fl_size)
            self.compression_ratio = f"{conv_dif:0.1%}"

        else:
            self.conv_fl_size = "Not Converted"
            self.compression_ratio = "NA"
            if self.logger is not False:
                logging.info(f"Conversion Failed: {self.video_out.name} \n")
