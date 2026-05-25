from whitenoise.compress import Compressor
from whitenoise.storage import CompressedStaticFilesStorage


class GzipOnlyStaticFilesStorage(CompressedStaticFilesStorage):
    """WhiteNoise non-manifest storage that skips brotli compression.

    Brotli at WhiteNoise's default quality 11 takes ~25 min on this static
    tree; gzip alone gives ~85% of the wire-size benefit in seconds.
    """

    def create_compressor(self, **kwargs):
        kwargs.setdefault("use_brotli", False)
        return Compressor(**kwargs)
