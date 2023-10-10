from PIL import Image
from pathlib import Path
import pandas as pd
from .utils.file_utils import get_size_format, rename_dir
from tqdm.notebook import tqdm
import shutil
from PIL import UnidentifiedImageError


def _compress_save(img, width, height, quality, exp_fl):
    """
    Given the new width, height, and quality. Re-size and export an image to the
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
    if width is False or height is False:
        compress_img = img
    else:
        try:
            compress_img = img.resize((width, height), Image.LANCZOS)
        except OSError:
            return False
    try:
        # save the image with the corresponding quality and optimize set to True
        compress_img.save(exp_fl, quality=quality, optimize=True)
    except OSError:
        try:
            # convert the image to RGB mode first
            compress_img = img.convert("RGB")
            # save the image with the corresponding quality and optimize set to True
            compress_img.save(exp_fl, quality=quality, optimize=True)
        except OSError:
            return False
    return exp_fl.stat().st_size


def _get_new_width_height(new_size_ratio, image_w, image_h):
    """
    Determine a new width and height based on new_size_ratio
    if new_size_ratio is 'auto' then it will determine the new_size_ratio based on the
    image size.

    Parameters
    ----------
    new_size_ratio : float
        ratio to resize the image
    image_w : int
        image width
    image_h : int
        image height
    """
    if new_size_ratio == 'auto':
        if image_h > 1200:
            if image_h > 3000 or image_w > 3000:
                new_size_ratio = 0.5
            else:
                new_size_ratio = 0.7
        else:
            new_size_ratio = 1
    if new_size_ratio < 1.0:
        # if resizing ratio is below 1.0, then multiply width & height with this ratio
        # to reduce image size
        new_w = int(image_w * new_size_ratio)
        new_h = int(image_h * new_size_ratio)
    else:
        new_w = False
        new_h = False
    return new_w, new_h, new_size_ratio


def _get_quality(quality, image_size):
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
    if quality == 'auto':
        if image_size > 1100000:  # 1.05MB
            if image_size > 10000000:  # 9.54MB
                quality = 70
            else:
                quality = 80
        else:
            quality = 90
    return quality


def compress_img(image_path, new_size_ratio='auto', quality='auto', width=None, height=None,
                 to_jpg=True, export_path=False, proc_path=False):
    """Compression function that given an image path, it will compress the image to try to
    save space. It will return a dataframe with the results of the compression.

    Parameters
    ----------
    image_path : str
        path to the image file
    new_size_ratio : float, optional
        ratio to resize the image. The default is 'auto'.
    quality : int, optional
        quality of the image. The default is 'auto'.
    width : int, optional
        width of the image. The default is None.
    height : int, optional
        height of the image. The default is None.
    to_jpg : bool, optional
        if True, then it will export the image as a jpg. The default is True.
    export_path : str, optional
        path to export the compressed image. The default is False.
    proc_path : str, optional
        path to move the original image to after it's been processed. The default is False.
    """
    fl_dir = image_path.parent
    if proc_path is False:
        proc_path = fl_dir.joinpath('processed', image_path.name)
    if export_path is False:
        export_path = fl_dir.joinpath('compressed', image_path.name)

    if to_jpg:
        export_path = export_path.with_suffix('.jpg')
    # load the image to memory
    try:
        with Image.open(image_path) as img:

            # Get stats
            image_size = image_path.stat().st_size
            image_w, image_h = img.size

            # Determine if you need a new size
            new_w, new_h, new_size_ratio = _get_new_width_height(new_size_ratio,
                                                                 image_w,
                                                                 image_h)
            # determine quality
            quality = _get_quality(quality,
                                   image_size)

            compress = True
            attempts = 0
            if image_size < 200000:
                # Don't try to compress if it's under '195.31KB'
                status = 'NOT Compressed'
                compress = False
                new_image_size = image_size
                shutil.copy(image_path, export_path)
            while compress is True and attempts < 3:
                attempts += 1
                new_image_size = _compress_save(img,
                                                new_w,
                                                new_h,
                                                quality,
                                                export_path)
                status = 'Compressed'
                if new_image_size is False:
                    # if the image can't be resized then don't try to compress it
                    status = 'Failed'
                    compress = False
                    new_image_size = image_size
                elif new_image_size > 5000000:  # '4.77MB'
                    new_size_ratio -= 10
                    new_w, new_h, new_size_ratio = _get_new_width_height(new_size_ratio,
                                                                         image_w,
                                                                         image_h)
                    quality -= 10
                elif new_image_size > 2000000:  # '1.91MB'
                    quality -= 10
                else:
                    compress = False
            # Calculate Saving Diff
            if new_image_size == image_size:
                saving_diff_str = '-'
            else:
                saving_diff = (image_size - new_image_size)/image_size
                saving_diff_str = f"{saving_diff:.1%}"
            results = pd.DataFrame({'Image': [image_path],
                                    'Image_size': [get_size_format(image_size)],
                                    'Status': [status],
                                    'New_size': [get_size_format(new_image_size)],
                                    'Compress %': [saving_diff_str],
                                    'Attempts': [attempts],
                                    })
        if status != 'Failed':
            image_path.rename(proc_path)
    except UnidentifiedImageError:
        results = pd.DataFrame({'Image': [image_path],
                                'Image_size': ['-'],
                                'Status': ['Failed'],
                                'New_size': ['-'],
                                'Compress %': ['-'],
                                'Attempts': [0],
                                })
    return results


def get_files_to_compress(main_dir, organize_by_subdir=True, img_suffixes=['.jpg', '.jpeg', '.png']):
    """
    get list of image files to compress from a directory. This will iterate through all
    subdirectories

    Parameters
    ----------
    main_dir : str
        directory to search for files
    organize_by_subdir : bool, optional
        if True, then it will return a dictionary of files organized by the tope subdirectories.
        if False it will return a list of all image files in all subdirectories.
        The default is True.
    img_suffixes : list, optional
        list of image suffixes to search for. The default is ['.jpg', 'jpeg', '.png'].

    """
    if organize_by_subdir:
        sub_directories = [folder for folder in Path(main_dir).glob('*') if folder.is_dir()]
        files = {}
        for folder in sub_directories:
            subfiles = [fl for fl in folder.rglob('*') if fl.is_file()]
            subfiles = [fl for fl in subfiles if fl.suffix.lower() in img_suffixes]
            files[folder.name] = {'folder': folder,
                                  'subfiles': subfiles}
    else:
        files = [fl for fl in Path(main_dir).rglob('*') if fl.is_file()]
        files = [fl for fl in subfiles if fl.suffix.lower() in img_suffixes]

    return files


def compress_files_subdir(subdir_file_dict, starting_dir, compress_dir='compressed',
                          processed_dir='processed', img_suffixes=['.jpg', 'jpeg', '.png'],
                          stats_fl='compression_stats.csv'):
    """
    Compress all images in a directory and save them to a new directory.

    nuances:
    starting_dir is the directory where the files are located. The compressed_dir is used
    to rename the file path. For example, if the file is located in 'images/2020/01/01/image.jpg'
    and the compressed_dir is 'compressed', then the new file path will be
    'compressed/2020/01/01/image.jpg'

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
    """
    compress_stats = []

    files_to_compress = {}
    folders = list(subdir_file_dict.keys())
    for fidx, folder in enumerate(tqdm(folders, desc='Total Compression')):
        files_to_compress = {}
        files = []
        subfiles = subdir_file_dict[folder]['subfiles']
        for fl in subfiles:
            comp_fl = rename_dir(fl, starting_dir, compress_dir)
            proc_fl = rename_dir(fl, starting_dir, processed_dir)
            if comp_fl.parent.is_dir() is False:
                comp_fl.parent.mkdir(parents=True)
            if proc_fl.parent.is_dir() is False:
                proc_fl.parent.mkdir(parents=True)
            files_to_compress[fl] = {'comp_fl': comp_fl, 'proc_fl': proc_fl}
            files.append(fl)

        for flid, fl in enumerate(tqdm(files, desc=f'{folder}: ')):
            comp_fl = files_to_compress[fl]['comp_fl']
            proc_fl = files_to_compress[fl]['proc_fl']
            stats = compress_img(fl,
                                 new_size_ratio='auto',
                                 quality='auto',
                                 width=None,
                                 height=None,
                                 to_jpg=True,
                                 export_path=comp_fl,
                                 proc_path=proc_fl)
            compress_stats.append(stats)
    if len(compress_stats) > 0:
        compress_stats = pd.concat(compress_stats, ignore_index=True)

        if stats_fl is not False:
            compress_stats.to_csv(stats_fl)
    else:
        compress_stats = False

    return compress_stats
