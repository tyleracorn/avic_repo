from pathlib import Path
import ffmpeg
import copy
import datetime
import json
import pandas as pd

from .utils import get_size_format


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
    output_file = output_dict['file']
    try:
        output_video_stream = video_stream.filter('scale',  **output_dict['scale'])
        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(output_file),
                                           **output_dict['settings'])
        video_audio_stream.overwrite_output().run()
        return True
    except Exception as e:
        print(e)
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
    output_file = output_dict['file']
    try:
        output_video_stream = video_stream
        video_audio_stream = ffmpeg.output(output_video_stream,
                                           audio_stream,
                                           str(output_file),
                                           **output_dict['settings'])
        video_audio_stream.overwrite_output().run()
        return True
    except:
        return False


def convert_videos(converted_files_info, videos_to_convert):
    """
    Convert videos in videos_to_convert dictionary and update converted_files_info dictionary

    Parameters
    ----------
    converted_files_info : dict
        dictionary of converted files info
    videos_to_convert : dict
        dictionary of videos to convert

    """
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
    for actor, actor_videos in videos_to_convert.items():
        print(f"Starting on {actor}")
        for vid, vid_settings in actor_videos.items():
            fl_in = copy.copy(vid_settings['path'])
            flsize = fl_in.stat().st_size
            output_dict = vid_settings['output']
            output_file = copy.copy(output_dict['file'])
            out_vid_height = output_dict['video_height']

            date = datetime.datetime.now().strftime("%Y-%m-%d")

            df_settings['name'].append(actor)
            df_settings['source_file'].append(vid)
            df_settings['output_file'].append(output_file.name)
            df_settings['source_size'].append(get_size_format(flsize))
            df_settings['source_vid_height'].append(vid_settings['video_height'])
            df_settings['source_frmt'].append(vid_settings['videocodex'])
            df_settings['date'].append(date)
            df_settings['out_frmt'].append('mp4')
            df_settings['out_vid_height'].append(out_vid_height)

            converted = False
            if vid_settings['videocodex'] == 'skip':
                converted_files_info[actor][vid] = 'Skipped'

            else:
                converted_files_info[actor][vid] = 'Converting'
                conv_str = f"Converting: {vid_settings['videocodex']}, from {vid_settings['video_height']}"
                conv_str += f" to {out_vid_height}"
                converted_files_info[actor][vid] = conv_str

                if output_file.is_file():
                    converted_files_info[actor][vid] = "Already Converted"

                    converted = True
                else:
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
            else:
                df_settings['out_size'].append('Not Converted')
                df_settings['size_comp'].append("NA")

            df_out = pd.DataFrame(df_settings)
            df_out.to_csv(f'converte_meta-{date}.csv')
            with open(f'converted_files_{date}.json', 'w') as jsfl:
                json.dump(converted_files, jsfl, indent=2)
