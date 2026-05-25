from whitenoise.compress import Compressor
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """WhiteNoise manifest storage that tolerates broken sourcemap references
    and skips brotli compression.

    - Vendored libraries in static/assets occasionally reference .map files
      that weren't shipped with the build. Django's default storage aborts
      collectstatic on the first such reference; this subclass leaves the
      reference unhashed and continues.
    - Brotli at WhiteNoise's default quality 11 takes ~25 min on this static
      tree. Gzip alone gives ~85% of the wire-size benefit in seconds, so
      we skip brotli entirely.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name

    def create_compressor(self, **kwargs):
        kwargs.setdefault("use_brotli", False)
        return Compressor(**kwargs)
