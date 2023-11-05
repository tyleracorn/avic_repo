from pathlib import Path
import ffmpeg
import copy
import pandas as pd
from tqdm.notebook import tqdm
from .utils.file_utils import get_size_format, rename_dir
from .utils.utils import get_date, get_date_12hr_min
import logging

_s = ' '
_2s = 2*_s
_4s = 4*_s


def output_with_scale(video_stream, audio_stream, output_dict):
    """
    Output video with scaling

    Parameters
    ----------
    video_stream : ffmpeg stream
        video stream
    audio_stream : ffmpeg stream
        audio stream
    output_dict : dict
        dictionary of output settings

    """
    output_file = output_dict['file_comp']
    try:
        output_video_stream = video_stream.filter('scale',  **output_dict['scale'])
        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(output_file),
                                           **output_dict['settings'])
        video_audio_stream.overwrite_output().run()
        return True
    except:
        logging.exception("output_with_scale failed")
        return False


def output_no_scale(video_stream, audio_stream, output_dict):
    """
    Output video without scaling

    Parameters
    ----------
    video_stream : ffmpeg stream
        video stream
    audio_stream : ffmpeg stream
        audio stream
    output_dict : dict
        dictionary of output settings
    """
    output_file = output_dict['file_comp']
    try:
        output_video_stream = video_stream
        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(output_file),
                                           **output_dict['settings'])
        video_audio_stream.overwrite_output().run()
        return True
    except:
        logging.exception("output_no_scale failed")
        return False


def _make_output_dirs(output_file, proccessed_file):
    """check if output and proccessed directories exist, if not create them"""
    if output_file.parent.is_dir() is False:
        output_file.parent.mkdir(parents=True)
    if proccessed_file.parent.is_dir() is False:
        proccessed_file.parent.mkdir(parents=True)

def convert_videos(videos_to_convert):
    """
    Convert videos in videos_to_convert dictionary and update converted_files_info dictionary

    Parameters
    ----------
    videos_to_convert : dict
        dictionary of videos to convert

    """

    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
    if Path('log_file.txt').is_file():
        Path('log_file.txt').unlink()

    logging.basicConfig(filename='log_file.txt', level=logging.INFO)
    date_time = get_date_12hr_min()
    logging.info(f'Started Conversion: {date_time} \n')
    df_settings = {'name': [],
                   'source_file': [],
                   'output_file': [],
                   'source_vid_height': [],
                   'out_vid_height': [],
                   'source_frmt': [],
                   'out_frmt': [],
                   'source_size': [],
                   'out_size': [],
                   'size_comp': [],
                   'date': []}
    folders = list(videos_to_convert.keys())
    for fidx, subdir in enumerate(tqdm(folders, desc='Total Compression')):
        logging.info(f"{_2s}Starting on {subdir}:")
        videos = list(videos_to_convert[subdir].keys())
        for vidx, vid in enumerate(tqdm(videos, desc=f"Compression: {subdir}")):
            vid_settings = videos_to_convert[subdir][vid]

            fl_in = copy.copy(vid_settings['path'])
            flsize = fl_in.stat().st_size
            output_dict = vid_settings['output']
            output_file = copy.copy(output_dict['file_comp'])

            proccessed_file = copy.copy(output_dict['file_proc'])
            _make_output_dirs(output_file, proccessed_file)
            out_vid_height = output_dict['video_height']
            date = get_date()

            conv_str = f"from {vid_settings['video_height']} to {out_vid_height}"
            logging.info(f"{_4s}converting {vid}: {conv_str}")

            df_settings['name'].append(subdir)
            df_settings['source_file'].append(vid)
            df_settings['output_file'].append(output_file.name)
            df_settings['source_size'].append(get_size_format(flsize))
            df_settings['source_vid_height'].append(vid_settings['video_height'])
            df_settings['source_frmt'].append(vid_settings['videocodex'])
            df_settings['date'].append(date)
            df_settings['out_frmt'].append('mp4')
            df_settings['out_vid_height'].append(out_vid_height)

            converted = False

            video_stream = ffmpeg.input(str(fl_in)).video
            audio_stream = ffmpeg.input(str(fl_in)).audio

            if out_vid_height == 480:
                converted = output_no_scale(video_stream,
                                            audio_stream,
                                            output_dict)
            if not converted:
                converted = output_with_scale(video_stream,
                                              audio_stream,
                                              output_dict)
                conv_fl_size = output_file.stat().st_size
            if converted:
                conv_fl_size = output_file.stat().st_size
                conv_dif = conv_fl_size/flsize

                df_settings['out_size'].append(get_size_format(conv_fl_size))
                df_settings['size_comp'].append(f"{conv_dif:0.1%}")
                # move file to processed folder
                fl_in.rename(proccessed_file)
            else:
                df_settings['out_size'].append('Not Converted')
                df_settings['size_comp'].append("NA")
                logging.info(f"{_4s}***Conversion Failed***")


            df_out = pd.DataFrame(df_settings)
            df_out.to_csv(f'converte_meta-{date}.csv')

