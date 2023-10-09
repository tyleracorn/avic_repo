import ffmpeg


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


def get_video_codec(fl):
    """Determine the video codec of a file

    Parameters
    ----------
    fl : Path
        path to video file

    Returns
    -------
    str : video codec
        video codec of the file. Possible values are: ['mp4', 'avi', 'mkv', 'unknown']"""
    if fl.suffix == ".mp4":
        return "mp4"
    elif fl.suffix == ".avi":
        return "avi"
    elif fl.suffix == ".mkv":
        return "mkv"
    else:
        return "unknown"


def setup_dictionaries(vid_folder_in):
    """Setup dictionaries for videos to convert and converted files info

    Parameters
    ----------
    vid_folder_in : Path
        path to video folder

    Returns
    -------
    videos_to_convert : dict
        dictionary of videos to convert in the format:
        {actor: {video_name: {path: Path,
                              videocodec: str,
                              output: {settings: dict,
                                       scale: dict,
                                       video_height: int,
                                       file: Path
                                       }
                              }
                }
        }
    """
    videos_to_convert = {}
    converted_files_info = {}
    for fld in vid_folder_in.glob('*'):
        if fld.is_dir():
            name = fld.name
            converted_files_info[name] = {}
            videos_to_convert[name] = {}
            for fl in fld.glob('*'):
                converted_files_info[name][fl.name] = "Found"
                videos_to_convert[name][fl.name] = {'path': fl}
    return videos_to_convert, converted_files_info


def setup_output_folder(vid_folder_out, actor):
    """Create the output folder for a given video folder name

    Parameters
    ----------
    vid_folder_out : Path
        path to output folder
    actor : str
        name of actor
    """
    outfolder = vid_folder_out.joinpath(actor)
    if not outfolder.is_dir():
        outfolder.mkdir()
    return outfolder


def set_output_settings(meta: dict, vid_settings: dict, outfolder, fl):
    """Set output settings based on video height

    Parameters
    ----------
    meta : dict
        dictionary of video metadata
    vid_settings : dict
        dictionary of video settings
    outfolder : Path
        path to output folder
    fl : Path
        path to video file
    """
    video_height = meta['video']['height']
    vid_settings['video_height'] = video_height
    vid_settings['output'] = {}
    vid_settings['output']['settings'] = {'b:v': '512K',
                                          'c:v': 'libx264',
                                          'c:a': 'copy'}

    if video_height == 1080:
        convert_to = 720
        vid_settings['output']['settings']['b:v'] = '1M'
    elif video_height >= 480:
        convert_to = 480
    else:
        convert_to = video_height
    vid_settings['output']['scale'] = {'width': -2,
                                       'height': convert_to}
    vid_settings['output']['video_height'] = convert_to
    output_file = outfolder.joinpath(f"{fl.stem}_converted_{convert_to}p.mp4")
    vid_settings['output']['file'] = output_file
    return vid_settings


def parse_names_files(vid_folder_in, vid_folder_out):
    """Parse video names and files

    Parameters
    ----------
    vid_folder_in : Path
        path to video folder
    vid_folder_out : Path
        path to output folder

    """
    videos_to_convert, converted_files_info = setup_dictionaries(vid_folder_in)

    for actor, actor_videos in videos_to_convert.items():
        outfolder = setup_output_folder(vid_folder_out, actor)

        for vid, vid_settings in actor_videos.items():
            fl = vid_settings['path']
            info = ffmpeg.probe(fl)
            streams = info['streams']
            meta = get_video_metadata(fl)
            vid_settings['videocodex'] = get_video_codec(fl)
            vid_settings = set_output_settings(meta, vid_settings, outfolder, fl)

    return converted_files_info, videos_to_convert
