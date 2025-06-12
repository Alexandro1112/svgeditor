from ctypes import c_void_p, c_char_p, c_int, POINTER, CDLL, byref, CFUNCTYPE, c_ubyte, c_uint
import subprocess
import re
from typing import Optional, Tuple, Union
import io
import ctypes.util
import platform

import bs4

class SurfaceXmlRenderingFormatError(Exception):
    """Raised when a SurfaceXmlRenderingFormatError is encountered."""


class DependencyError(Exception):
    """Raised when required dependencies are missing."""


class InvalidFileExtensionError(Exception):
    """Raised when file extensions are incorrect."""


class SVGParseError(Exception):
    """Raised when parsing SVG dimensions fails."""


class CairoRenderError(Exception):
    """Raised when Cairo rendering operations fail."""


class XmlGraphic(bytes):
    def __init__(self, xml: bytes):
        self.xml = xml
        xml = bs4.BeautifulSoup(self.xml, 'xml').find('svg')
        self.w, self.h = xml.get('width'), xml.get('height')

    def render(self):
        return self.xml

    def size(self):
        return int(self.w[:len(self.w)-2]), int(self.h[:len(self.h)-2])



class SvgImageSurface:
    def __init__(
            self,
            from_file: Optional[str | XmlGraphic],
            to_file: Optional[str] = None,
            save_bg: bool = True,
            width: Optional[Union[int, float]] = None,
            height: Optional[Union[int, float]] = None
    ):
        """Initialize surface for rendering SVG to PNG."""
        self.save_bg = save_bg
        self.from_file = from_file
        self.to_file = to_file

        # Validate file extensions
        if isinstance(self.from_file, str):
            if not self.from_file.endswith('.svg'):
                raise InvalidFileExtensionError('from_file must end with .svg')
            if self.to_file and not self.to_file.endswith('.png'):
                raise InvalidFileExtensionError('to_file must end with .png')

        # Get SVG dimensions if not provided
        self.width, self.height = self._get_svg_dimensions(width, height)

        # Load libraries and define functions
        self._load_libraries()
        self._define_function_types()

    def _get_svg_dimensions(
            self,
            width: Optional[Union[int, float]] = None,
            height: Optional[Union[int, float]] = None
    ) -> Tuple[float, float]:
        """Parse SVG dimensions from file if not provided."""
        if width is not None and height is not None:
            return width, height

        try:
            with open(self.from_file, 'r') as f:
                content = f.read()
        except IOError as e:
            raise SVGParseError(f"Error reading SVG file: {e}") from e

        # Parse dimensions using regex
        width_match = re.search(r'<svg[^>]*width="([\d.]+)"', content)
        height_match = re.search(r'<svg[^>]*height="([\d.]+)"', content)


        if width_match and height_match:
            return float(width_match.group(1)), float(height_match.group(1))

        # Try to parse viewBox as fallback
        viewbox_match = re.search(r'<svg[^>]*viewBox="[^"]*\s([\d.]+)\s([\d.]+)"', content)
        if viewbox_match:
            return float(viewbox_match.group(1)), float(viewbox_match.group(2))

        # Try to extract from style attribute
        style_match = re.search(r'<svg[^>]*style="[^"]*width:\s*([\d.]+)px;[^"]*height:\s*([\d.]+)px;"', content)
        if style_match:
            return float(style_match.group(1)), float(style_match.group(2))

        raise SVGParseError('Could not determine SVG dimensions')

    def _load_libraries(self) -> None:
        """Load required libraries with proper error handling."""
        # Try standard library names
        cairo_name = 'cairo'
        librsvg_name = 'librsvg'

        if platform.system() == 'Darwin':
            try:
                versions = {}
                for names in [cairo_name, librsvg_name]:
                    dll, version = subprocess.check_output(['brew', 'list', names, '--version']).split()
                    versions[dll.decode()] = str(version.decode())

                self.librsvg = CDLL('/opt/homebrew/Cellar/librsvg/%s/lib/librsvg-2.dylib' % versions['librsvg'])
                self.cairo = CDLL('/opt/homebrew/Cellar/cairo/%s/lib/libcairo.2.dylib' % versions['cairo'])
                return

            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                pass

        self.cairo = CDLL(ctypes.util.find_library(cairo_name))
        self.librsvg = CDLL(ctypes.util.find_library(librsvg_name))

        if not self.cairo or not self.librsvg:
            raise DependencyError(
                'Cairo and librsvg libraries not found in system paths')

    def _define_function_types(self) -> None:
        """Define ctypes signatures for library functions."""
        # Cairo function definitions
        self.cairo.cairo_image_surface_create.argtypes = [c_int, c_int, c_int]
        self.cairo.cairo_image_surface_create.restype = c_void_p

        self.cairo.cairo_create.argtypes = [c_void_p]
        self.cairo.cairo_create.restype = c_void_p

        self.cairo.cairo_image_surface_get_stride.argtypes = [c_void_p]
        self.cairo.cairo_image_surface_get_stride.restype = c_void_p

        self.cairo.cairo_image_surface_get_format.argtypes = [c_void_p]
        self.cairo.cairo_image_surface_get_format.restype = c_void_p

        self.cairo.cairo_surface_write_to_png.argtypes = [c_void_p, c_char_p]
        self.cairo.cairo_surface_write_to_png.restype = c_int

        self.cairo.cairo_surface_destroy.argtypes = [c_void_p]
        self.cairo.cairo_surface_destroy.restype = None

        self.cairo.cairo_destroy.argtypes = [c_void_p]
        self.cairo.cairo_destroy.restype = None

        # Add PNG stream function
        self.cairo.cairo_surface_write_to_png_stream.argtypes = [
            c_void_p,
            CFUNCTYPE(c_int, c_void_p, POINTER(c_ubyte), c_uint),
            c_void_p
        ]
        self.cairo.cairo_surface_write_to_png_stream.restype = c_int

        #self.cairo.cairo_status_to_string.argtypes = [c_void_p]  # deprecated in 0.0.1 version
        #self.cairo.cairo_status_to_string.restype = c_void_p

        # RSVG function definitions
        self.librsvg.rsvg_handle_new_from_file.argtypes = [c_char_p, POINTER(c_void_p)]
        self.librsvg.rsvg_handle_new_from_file.restype = c_void_p

        self.librsvg.rsvg_handle_render_cairo.argtypes = [c_void_p, c_void_p]
        self.librsvg.rsvg_handle_render_cairo.restype = c_int

        self.librsvg.rsvg_handle_close.argtypes = [c_void_p, POINTER(c_void_p)]
        self.librsvg.rsvg_handle_close.restype = None

        self.librsvg.rsvg_handle_new_from_data.argtypes = [c_char_p, c_int, c_void_p]
        self.librsvg.rsvg_handle_new_from_data.restype = c_void_p



    def _render(self) -> Tuple[c_void_p, c_void_p, c_void_p]:
        """Core rendering logic with resource management."""
        error = c_void_p()
        handle = None
        if isinstance(self.from_file, XmlGraphic):  # if passed svg graphical xml format
            content = bs4.BeautifulSoup(XmlGraphic(self.from_file).render(), 'xml').find('svg')
            if content:
                handle = self.librsvg.rsvg_handle_new_from_data(
                    XmlGraphic(self.from_file).render(),
                    len(self.from_file),
                    byref(error)
                )
            else:
                raise SurfaceXmlRenderingFormatError('Passed wrong xml format that not supports .svg')

        if isinstance(self.from_file, str):
            handle = self.librsvg.rsvg_handle_new_from_file(
                self.from_file.encode('utf-8'),
                byref(error)
            )
        if not handle:
            raise CairoRenderError(f'Error loading SVG: {self.cairo.cairo_status_to_string(error)}')

        surface_format = 0x0000 if not self.save_bg else 0x0001  # ARGB32 (with alpha) vs RGB24 (no alpha)
        surface = self.cairo.cairo_image_surface_create(
            surface_format,
            int(self.width),
            int(self.height)
        )
        context = self.cairo.cairo_create(surface)

        render_status = self.librsvg.rsvg_handle_render_cairo(handle, context)
        if render_status != 1:
            self._cleanup_resources(handle, context, surface)
            raise CairoRenderError(f'Rendering failed with status: {hex(render_status)}')

        return handle, context, surface

    def _cleanup_resources(
            self,
            handle: c_void_p,
            context: c_void_p,
            surface: c_void_p
    ) -> None:
        """Safely release rendering resources."""
        if context and self.cairo.cairo_destroy:
            self.cairo.cairo_destroy(context)
        if surface and self.cairo.cairo_surface_destroy:
            self.cairo.cairo_surface_destroy(surface)
        if handle and self.librsvg.rsvg_handle_close:
            self.librsvg.rsvg_handle_close(handle, None)

    def _save(self) -> int:
        """Render SVG to PNG file."""
        if not self.to_file:
            raise ValueError('Output file path not specified')

        handle, context, surface = self._render()
        try:
            status = self.cairo.cairo_surface_write_to_png(
                surface,
                self.to_file.encode()
            )
            if status != 0:
                raise CairoRenderError(f'PNG write failed with status: {hex(status)}')
        finally:
            self._cleanup_resources(handle, context, surface)


    def _tobytes(self) -> bytes:
        """Render SVG to PNG bytes in memory."""
        handle, context, surface = self._render()
        try:
            buffer = io.BytesIO()

            @CFUNCTYPE(c_int, c_void_p, POINTER(c_ubyte), c_uint)
            def write_callback(_: c_void_p, data: POINTER(c_ubyte), length) -> int:
                buffer.write(bytearray(data[:length]))
                return 0  # CAIRO_STATUS_SUCCESS

            status = self.cairo.cairo_surface_write_to_png_stream(
                surface,
                write_callback,
                None
            )
            if status != 0:
                raise CairoRenderError(f'PNG stream failed with status: {hex(status)}')

            return buffer.getvalue()
        finally:
            self._cleanup_resources(handle, context, surface)

    def _stride(self):
        handle, context, surface = self._render()
        return self.cairo.cairo_image_surface_get_stride(surface)
