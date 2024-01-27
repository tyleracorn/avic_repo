from .image_compression import ImageCompress, MultiImageCompression
from .video_compress_class import VideoCompress, MultiVideoCompress
from .video_compression import convert_videos, output_no_scale, output_with_scale
from .manga_compression import compress_manga_images, get_zip_file_dicts
from . import utils

del image_compression
del video_compression
del manga_compression
del video_compress_class