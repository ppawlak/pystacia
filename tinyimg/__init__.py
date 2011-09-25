import webbrowser
from sys import argv
from os.path import dirname, join, exists
from bz2 import BZ2File
import atexit
from tempfile import mkstemp
from ctypes import CDLL, c_size_t, byref, string_at
from ctypes.util import find_library
from collections import Sequence

from .types import Filter

def init():
    global cdll
    cdll = CDLL(find_library('magickWand'))
    
    if not cdll: raise TinyException('Could not find or load magickWand')
    
    from .func import annote
    annote(cdll)
    
    cdll.MagickWandGenesis()
    atexit.register(lambda: cdll.MagickWandTerminus())

class TinyException(Exception): pass

def only_live(f):
    def wrapper(image, *args, **kw):
        if image.closed: raise TinyException('Image already closed')
        
        return f(image, *args, **kw)
        
    return wrapper

def read(filename=None, file=None):
    return Image.read(filename, file)

def lena_blob():
    with BZ2File(join(dirname(__file__), 'lena.ycbcr.bz2')) as f:
        return dict(blob=f.read(), format='ycbcr', height=512, width=512, depth=8)

def lena(size=None):
    img = Image(**lena_blob())
    if size: img.resize(size, size)
    
    return img

def get_magick_version_str():
    return cdll.MagickGetVersion(None)

__magick_version = None
def get_magick_version():
    global __magick_version
    
    if not __magick_version:
        options = get_magick_options()
        
        try: version = options['LIB_VERSION_NUMBER']
        except KeyError:
            try: version = options['VERSION']
            except KeyError: pass
            else: __magick_version = tuple(int(x) for x in version.splut('.'))
        else: __magick_version = tuple(int(x) for x in version.split(','))
        
    return __magick_version

__magick_options = {}
def get_magick_options():
    global __magick_options
    
    if not __magick_options:
        size = c_size_t()
        keys = cdll.MagickQueryConfigureOptions('*', size)
        for key in (keys[i] for i in range(size.value)):
            __magick_options[key] = cdll.MagickQueryConfigureOption(key)
            
    return __magick_options
    

class Image(object):
    def __init__(self, width=None, height=None, depth=None,
                 format=None, blob=None, wand=None, debug=False):
        self.__wand = wand if wand else cdll.NewMagickWand()
        
        self.debug = debug

        if blob:
            try: blob = blob.read()
            except AttributeError: pass
            if width and height:
                guard(self.__wand, lambda: cdll.MagickSetSize(self.__wand, width, height))
            if depth:
                guard(self.__wand, lambda: cdll.MagickSetDepth(self.__wand, depth))
            if format:
                format = format.upper()
                guard(self.__wand, lambda: cdll.MagickSetFormat(self.__wand, format))
            guard(self.__wand, lambda: cdll.MagickReadImageBlob(self.__wand, blob, len(blob)))
            
        self.__closed = False
        
        if not self.__wand:
            raise TinyException('Couldnt initialize image')
    
    def clone(self):
        wand = cdll.CloneMagickWand(self.__wand)
        return self.__class__(wand=wand)
    
    @classmethod
    def read(cls, filename=None, file=None):
        wand = cdll.NewMagickWand()
        
        if file:
            return cls(blob=file)
        
        if filename:
            if not exists(filename):
                raise IOError((2, 'No such file or directory: {0}'.format(filename)))
            guard(wand, lambda: cdll.MagickReadImage(wand, filename))
            return cls(wand=wand)
    
    @only_live
    def write(self, filename):
        guard(self.__wand, lambda: cdll.MagickWriteImage(self.__wand, filename))
        
    @only_live
    def get_blob(self, format=None):
        if format:
            format = format.upper()
            old_format = cdll.MagickGetImageFormat(self.__wand)
            guard(self.__wand,
                  lambda: cdll.MagickSetImageFormat(self.__wand, format),
                  'Format "{0}" unsupported'.format(format))
        
        size = c_size_t()
        result = guard(self.__wand, lambda: cdll.MagickGetImageBlob(self.__wand, byref(size)))
        blob = string_at(result, size.value)
        cdll.MagickRelinquishMemory(result)
        
        if format:
            guard(self.__wand, lambda: cdll.MagickSetImageFormat(self.__wand, old_format))
        
        return blob
        
    @only_live
    def resize(self, width=None, height=None, factor=None, filter=None, blur=1):
        if not filter: filter = 'undefined'
        
        if not width and not height:
            if not factor:
                raise TinyException('Either width, height or factor must be provided')
            
            width, height = self.size
            if not isinstance(factor, Sequence): factor = (factor, factor)
            width, height = int(width * factor[0]), int(height * factor[1])
        
        filter = getattr(Filter, filter.upper())
        
        guard(self.__wand, lambda: cdll.MagickResizeImage(self.__wand, width, height, filter, blur))
    
    @only_live
    def crop(self, width, height, x=0, y=0):
        guard(self.__wand, lambda: cdll.MagickCropImage(self.__wand, width, height, x, y))
    
    @only_live
    def flip(self, axis):
        if axis.upper() == 'X':
            guard(self.__wand, lambda: cdll.MagickFlipImage(self.__wand))
        elif axis.upper() == 'Y':
            guard(self.__wand, lambda: cdll.MagickFlopImage(self.__wand))
        else:
            raise TinyException('axis must be X or Y')
        
    @only_live
    def roll(self, x, y):
        guard(self.__wand, lambda: cdll.MagickRollImage(self.__wand, x, y))
        
    @only_live
    def despeckle(self):
        guard(self.__wand, lambda: cdll.MagickDespeckleImage(self.__wand))
        
    @only_live
    def emboss(self, radius=0, sigma=0):
        guard(self.__wand, lambda: cdll.MagickEmbossImage(self.__wand, radius, sigma))
    
    @only_live
    def enhance(self):
        guard(self.__wand, lambda: cdll.MagickEnhanceImage(self.__wand))
    
    @only_live
    def equalize(self):
        guard(self.__wand, lambda: cdll.MagickEqualizeImage(self.__wand))
        
    @only_live
    def dft(self, magnitude):
        guard(self.__wand, lambda: cdll.MagickForwardFourierTransformImage(self.__wand, bool(magnitude)))
    
    @only_live
    def eval(self, expression):
        wand = guard(self.__wand, lambda: cdll.MagickFxImage(self.__wand, expression))
        cdll.DestroyMagickWand(self.__wand)
        self.__wand = wand
    
    @only_live
    def gamma(self, gamma):
        guard(self.__wand, lambda: cdll.MagickGammaImage(self.__wand, gamma))
    
    @only_live
    def swirl(self, degrees):
        guard(self.__wand, lambda: cdll.MagickSwirlImage(self.__wand, degrees))
        
    @only_live
    def spread(self, radius):
        guard(self.__wand, lambda: cdll.MagickSpreadImage(self.__wand, radius))
        
    @only_live
    def auto_gamma(self):
        guard(self.__wand, lambda: cdll.MagickAutoGammaImage(self.__wand))
    
    @only_live
    def auto_level(self):
        guard(self.__wand, lambda: cdll.MagickAutoLevelImage(self.__wand))
        
    @only_live
    def blur(self, radius=0, sigma=0):
        guard(self.__wand, lambda: cdll.MagickBlurImage(self.__wand, radius, sigma))
    
    @only_live
    def brightness(self, percent):
        guard(self.__wand, lambda: cdll.MagickBrightnessContrastImage(self.__wand, percent, 0))
    
    @only_live
    def contrast(self, percent):
        guard(self.__wand, lambda: cdll.MagickBrightnessContrastImage(self.__wand, 0, percent))
    
    @property
    @only_live
    def width(self):
        return cdll.MagickGetImageWidth(self.__wand)
    
    @property
    @only_live
    def height(self):
        return cdll.MagickGetImageHeight(self.__wand)
    
    @property
    def size(self):
        return (self.width, self.height)
    
    @property
    def debug(self):
        return bool(self.__wand.contents.debug)
    
    @debug.setter
    def debug(self, value):
        self.__wand.contents.debug = value
    
    @property
    @only_live
    def depth(self):
        return cdll.MagickGetImageDepth(self.__wand)
    
    def show(self):
        tmpname = mkstemp()[1] + '.bmp'
        self.write(tmpname)
        webbrowser.open('file://' + tmpname)
    
    @only_live
    def close(self):
        cdll.DestroyMagickWand(self.__wand)
        self.__wand = None
        self.__closed = True
    
    @property
    def closed(self): return self.__closed
    
    def __del__(self):
        if not self.__closed: self.close()

init()

from .func import guard

__all__ = [Image, lena, read]