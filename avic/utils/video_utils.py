import ffmpeg
from .file_utils import get_size_format, rename_dir, delete_empty_dir


_video_suffixes = ['.mp4', '.m4v', '.mpg', '.mpeg', '.avi', '.mkv', '.mov', '.wmv', '.mts','.ts']


def _get_video_codec(fl):
    """Determine the video codec of a file

    Parameters
    ----------
    fl : Path
        path to video file

    Returns
    -------
    str : video codec
        video codec of the file. Possible values are: ['mp4', 'avi', 'mkv', 'unknown']"""
    if fl.suffix.lower() in [".mp4", ".m4v", '.mpg', '.mpeg', '.mts', '.ts']:
        return "mp4"
    elif fl.suffix.lower() == ".avi":
        return "avi"
    elif fl.suffix.lower() == ".mkv":
        return "mkv"
    elif fl.suffix.lower() == ".mov":
        return "mov"
    elif fl.suffix.lower() == ".wmv":
        return "wmv"
    else:
        return "unknown"


def _setup_dictionaries(vid_folder_in,
                        video_suffixes='default'):
    """Setup dictionaries for videos to convert and converted files info

    Parameters
    ----------
    vid_folder_in : Path
        path to video folder
    video_suffixes : list, optional
        list of video suffixes to convert, by default 'default' which is:
        ['.mp4', '.m4v', '.mpg', '.mpeg', '.avi', '.mkv', '.mov', '.wmv', '.mts','.ts']

    Returns
    -------
    videos_to_convert : dict
        dictionary of videos to convert in the format:
        {subdir: {video_name: {path: Path,
                               status: 'Found'}
                  }
        }
    """
    if video_suffixes == 'default':
        video_suffixes = _video_suffixes
    videos_to_convert = {}
    for fld in vid_folder_in.glob('*'):
        if fld.is_dir():
            name = fld.name
            videos_to_convert[name] = {}
            for fl in fld.glob('*'):
                if fl.suffix.lower() in video_suffixes:
                    videos_to_convert[name][fl.name] = {'path': fl,
                                                        'status': 'Found'}
    return videos_to_convert


def _set_output_settings(meta: dict, vid_settings: dict, flname, vid_folder_in, vid_folder_out,
                         vid_folder_proc):
    """Set output settings based on video height

    Parameters
    ----------
    meta : dict
        dictionary of video metadata
    vid_settings : dict
        dictionary of video settings
    outfolder : Path
        path to output folder
    """
    video_height = meta['video']['height']
    vid_settings['video_height'] = video_height
    vid_settings['output'] = {}
    vid_settings['output']['settings'] = {'b:v': '512K',
                                          'c:v': 'libx264',
                                          'c:a': 'copy'}

    if video_height >= 1080:
        convert_to = 720
        vid_settings['output']['settings']['b:v'] = '1M'
    elif video_height >= 480:
        convert_to = 480
    else:
        convert_to = video_height
    vid_settings['output']['scale'] = {'width': -2,
                                       'height': convert_to}
    vid_settings['output']['video_height'] = convert_to

    # Set output filenames
    file_out = rename_dir(flname, vid_folder_in, vid_folder_out)
    file_out = file_out.with_stem(f"{flname.stem}_converted_{convert_to}p")
    file_out = file_out.with_suffix('.mp4')
    vid_settings['output']['file_comp'] = file_out
    vid_settings['output']['file_proc'] = rename_dir(flname, vid_folder_in, vid_folder_proc)

    return vid_settings


def get_video_metadata(fl):
    """Extract video metadata from a file

    Parameters
    ----------
    fl : Path
        path to video file

    Returns
    -------
    meta : dict
        dictionary of video metadata"""
    info = ffmpeg.probe(fl)
    streams = info['streams']
    meta = {}
    for strm in streams:
        if strm['codec_type'] == "video":
            meta['video'] = strm
        elif strm['codec_type'] == "audio":
            meta['audio'] = strm
    return meta


def parse_video_names_files(vid_folder_in, vid_folder_out, vid_folder_proc, video_suffixes='default'):
    """Parse video names and files

    Parameters
    ----------
    vid_folder_in : Path
        path to video folder
    vid_folder_out : Path
        path to output folder
    vid_fold_proc : Path
        path to move files to after processing
    video_suffixes : list, optional
        list of video suffixes to convert, by default 'default' which is:
        ['.mp4', '.m4v', '.mpg', '.mpeg', '.avi', '.mkv', '.mov', '.wmv', '.mts','.ts']

    """
    videos_to_convert = _setup_dictionaries(vid_folder_in, video_suffixes=video_suffixes)

    for subdir, video in videos_to_convert.items():

        for vid, vid_settings in video.items():
            fl = vid_settings['path']
            info = ffmpeg.probe(fl)
            # streams = info['streams']
            meta = get_video_metadata(fl)
            vid_settings['videocodex'] = _get_video_codec(fl)
            vid_settings = _set_output_settings(meta,
                                                vid_settings,
                                                flname=fl,
                                                vid_folder_in=vid_folder_in,
                                                vid_folder_out=vid_folder_out,
                                                vid_folder_proc=vid_folder_proc)


    return videos_to_convert
