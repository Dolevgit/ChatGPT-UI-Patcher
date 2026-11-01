"""Use the installed app's current flat icon in the copied executable."""
import ctypes
from ctypes import wintypes as w
import struct
import winreg


def source_icon(app):
    dark = True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            dark = not bool(winreg.QueryValueEx(key, 'SystemUsesLightTheme')[0])
    except OSError:
        pass
    return app / 'resources' / ('chatgpt-app-dark.ico' if dark else 'chatgpt-app-light.ico')


def icon_images(data):
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved or kind != 1 or not count or count > 100:
        raise RuntimeError('Invalid icon directory')
    images = []
    for i in range(count):
        width, height, colors, zero, planes, bits, size, offset = struct.unpack_from('<BBBBHHII', data, 6+i*16)
        if not size or offset < 6+count*16 or offset+size > len(data):
            raise RuntimeError('Invalid icon image')
        images.append(((width, height, colors, zero, planes, bits, size), data[offset:offset+size]))
    return images


def replace(executable, icon):
    images = icon_images(icon.read_bytes())
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
    kernel.LoadLibraryExW.restype = w.HMODULE
    kernel.FreeLibrary.argtypes = [w.HMODULE]
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HMODULE, ctypes.c_void_p, ctypes.c_void_p, w.LPARAM)
    language_callback = ctypes.WINFUNCTYPE(w.BOOL, w.HMODULE, ctypes.c_void_p, ctypes.c_void_p, w.WORD, w.LPARAM)
    kernel.EnumResourceNamesW.argtypes = [w.HMODULE, ctypes.c_void_p, callback_type, w.LPARAM]
    kernel.EnumResourceLanguagesW.argtypes = [w.HMODULE, ctypes.c_void_p, ctypes.c_void_p, language_callback, w.LPARAM]
    kernel.BeginUpdateResourceW.argtypes = [w.LPCWSTR, w.BOOL]
    kernel.BeginUpdateResourceW.restype = w.HANDLE
    kernel.UpdateResourceW.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, w.WORD, w.LPVOID, w.DWORD]
    kernel.EndUpdateResourceW.argtypes = [w.HANDLE, w.BOOL]
    module = kernel.LoadLibraryExW(str(executable), None, 2 | 0x20)
    if not module:
        raise ctypes.WinError(ctypes.get_last_error())
    names = []
    languages = {}
    @callback_type
    def collect(handle, kind, name, param):
        names.append(name if name <= 0xffff else ctypes.wstring_at(name))
        return True
    try:
        kernel.EnumResourceNamesW(module, ctypes.c_void_p(14), collect, 0)
        for name in names:
            languages[name] = []
            @language_callback
            def collect_language(handle, kind, resource, language, param):
                languages[name].append(language)
                return True
            pointer = ctypes.c_void_p(name) if isinstance(name, int) else ctypes.cast(ctypes.c_wchar_p(name), ctypes.c_void_p)
            kernel.EnumResourceLanguagesW(module, ctypes.c_void_p(14), pointer, collect_language, 0)
    finally:
        kernel.FreeLibrary(module)
    if not names:
        raise RuntimeError('Copied executable has no icon group')
    handle = kernel.BeginUpdateResourceW(str(executable), False)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    def update(kind, name, data, language):
        name_ptr = ctypes.c_void_p(name) if isinstance(name, int) else ctypes.cast(ctypes.c_wchar_p(name), ctypes.c_void_p)
        buffer = ctypes.create_string_buffer(data)
        if not kernel.UpdateResourceW(handle, ctypes.c_void_p(kind), name_ptr, language, buffer, len(data)):
            raise ctypes.WinError(ctypes.get_last_error())
    try:
        group = struct.pack('<HHH', 0, 1, len(images))
        for index, (metadata, data) in enumerate(images, 1):
            for language in {lang for values in languages.values() for lang in values}:
                update(3, index, data, language)
            group += struct.pack('<BBBBHHIH', *metadata, index)
        for name in names:
            for language in languages[name]:
                update(14, name, group, language)
    except BaseException:
        kernel.EndUpdateResourceW(handle, True)
        raise
    if not kernel.EndUpdateResourceW(handle, False):
        raise ctypes.WinError(ctypes.get_last_error())


def refresh(path):
    shell = ctypes.WinDLL('shell32')
    shell.SHChangeNotify(0x2000, 5, ctypes.c_wchar_p(str(path)), None)
