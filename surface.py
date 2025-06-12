from .unix import SvgSurface

class SVGSurface(SvgSurface):
    def __init__(self, from_file, to_file, save_bg, width, height):
        super().__init__(from_file, to_file, save_bg, width, height)

    def __repr__(self):
        return ('<%s context to rendering %s image from %s>'
                % (self.__class__.__name__, repr(self.from_file), repr(self.to_file)))

    def tobytes(self) -> bytes:
        return self._tobytes()

    def save(self):
        return self._save()

    def stride(self):
        return self._stride()