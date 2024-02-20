from pathlib import Path
from .utils.file_utils import get_size_format, rename_dir
import shutil
from .utils.logger import ClassWithLogger
import tempfile
import re
import xml.etree.ElementTree as ET


def _replace_elements(input_list, replacements):
    input_list = list(input_list)
    for i, element in enumerate(input_list):
        if element in replacements:
            input_list[i] = replacements[element]
    return input_list

def _remove_word(text, word, brackets=True, ignore_case=True):
    """Remove a word from a string

    Parameters
    ----------
    text : str
        text to remove word from
    word : str
        word to remove
    brackets : bool
        remove () or [] from around the word as well, by default True
    ignore_case : bool
        ignore case when removing word, by default True"""
    # replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    if ignore_case:
        flags = re.IGNORECASE
    else:
        flags = 0
    if brackets:
        pattern = re.compile(f'\[{word}\]', flags)
        text = pattern.sub('', text)

        pattern = re.compile(f'\({word}\)', flags)
        text = pattern.sub('', text)
    pattern = re.compile(f'{word}', flags)
    text = pattern.sub('', text)
    text = text.rstrip().lstrip()
    return text


class MangaManager(ClassWithLogger):
    def __init__(self, manga_file, proc_dir='finished', log_file=False, logger=None, l
                 evel=logging.INFO):
        super().__init__('MangaManager', log_file, logger, level)
        self.manga_file = Path(manga_file)
        if not self.manga_file.is_file():
            raise FileNotFoundError(f"{self.manga_file} does not exist")

        if proc_dir is False or proc_dir is None:
            self.proc_dir = self.manga_file.parent
        else:
            self.proc_dir = Path(proc_dir)
        self.unzip_dir = False

    def _unzip_manga(self):
        """unzip the manga file"""
        from .utils.file_utils import unzip_file

        unzip_file(self.manga_file, self.unzip_dir)
        self.logger.info(f"Manga unzipped to {self.unzip_dir}")

    def _zip_manga(self, delete_dir=False):
        """zip the manga file"""
        from .utils.file_utils import zip_manga_dir
        zip_manga_dir(self.unzip_dir, delete_dir=delete_dir)
        self.logger.info(f"Manga zipped")

    def load_xml(self):
        """Load the xml file"""
        self.xml_tree = ET.parse(self.comic_info_file)
        self.xml_root = self.xml_tree.getroot()

        self.xml_Title = self.xml_root.find('Title')
        self.xml_Pages = self.xml_root.find('Pages')
        self.xml_LanguageISO = self.xml_root.find('LanguageISO')
        if self.xml_LanguageISO is None:
            self._add_element('LanguageISO', '')
            self.xml_LanguageISO = self.xml_root.find('LanguageISO')

        self.xml_Genre = self.xml_root.find('Genre')
        if self.xml_Genre is None:
            self._add_element('Genre', '')
            self.xml_Genre = self.xml_root.find('Genre')
            self.tags = []
        else:
            self.tags = self.xml_Genre.text.split(',')
            self.tags = [tag.strip() for tag in self.tags]

    def _check_title_english(self, title):
        english = False
        if 'english' in title.text.lower():
            english = True
            title = _remove_word(title, 'english')
        if '[eng]' in title.text.lower():
            english = True
            title = _remove_word(title, '\[eng\]', ignore_case=True, brackets=False)

        if english:
            LanguageISO.text = 'en'

        return title

    def _check_title_uncen(self, title):
        uncen = False
        for word in ['decensored', 'uncensored']:
            if word in title.text.lower():
                uncen = True
                title = _remove_word(title, word)
        if '[uncen]' in title.text.lower():
            uncen = True
            title = _remove_word(title, '\[uncen\]', ignore_case=True, brackets=False)
        if '[decen]' in title.text.lower():
            uncen = True
            title = _remove_word(title, '\[uncen\]', ignore_case=True, brackets=False)
        self.tags.append('Uncensored')
        return title

    def _check_title_color(self, title):
        color = False
        if 'colorized' in title.text.lower():
            color = True
            title = _remove_word(title, 'colorized')

        if 'full color' in title.text.lower():
            color = True
            title = _remove_word(title, 'full color')
        if 'full colour' in title.text.lower():
            color = True
            title = _remove_word(title, 'full colour')
        if color:
            self.tags.append('Full Color')
        return title

    def _check_title_authour(self, title):
        values_found = []
        for key in ['Writer', 'Penciller', 'Inker', 'Letterer', 'CoverArtist', 'Editor']:
            elm = self.root.find(key)
            if elm is not None:
                if elm.text is not None:
                    value = elm.text
                    if value.lower() in title.text.lower():
                        values_found.append(value)
        values_found = list(set(values_found))
        for value in values_found:
            title = remove_word(title, value)
            title = remove_word(title, '\[ \]', brackets=False)
        return title

    def cleanup_title(self):
        """Clean up the title and get any tags from the title if needed"""
        title = self.xml_Title.text

        title = self._check_title_english(title)
        title = self._check_title_uncen(title)
        title = self._check_title_color(title)
        self.xml_Title.text = title

    def cleanup_pages(self):
        from PIL import Image
        for child in self.xml_Pages:
            if 'Key' in child.attrib:
                fl = Path(child.attrib['Key'])
                flpath = self.unzip_dir.joinpath(fl)
                if not flpath.is_file():
                    flpath = self.unzip_dir.joinpath(fl.name)
                if flpath.is_file():
                    child.attrib['ImageSize'] = flpath.stat().st_size
                    with Image.open(flpath) as img:
                        child.attrib['ImageWidth'] = img.width
                        child.attrib['ImageHeight'] = img.height
                else:
                    if self.logger is not False:
                        self.logger.warning(f"File {flpath} does not exist")
            else:
                if self.logger is not False:
                    self.logger.warning(f"Key not found in for image {child.attrib{'Image'}}")




    def save_xml(self):
        """Save the xml file"""
        self.xml_tree.write(self.comic_info_file)

    def cleanup_tags(tags):
        replacements = {'Decensored': 'Uncensored'}
        tags = _replace_elements(tags, replacements)
        tags = list(set(tags))
        return tags

    def _add_element(self, name, text):
        new_item = ET.Element(name)
        new_item.text = text
        self.root.append(new_item)

