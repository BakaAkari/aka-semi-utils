from jinja2 import pass_context

from core.config_loader import LOGOS_DIR as logos_dir


@pass_context
def vw(context, percent):
    exif = context.get('exif', {})
    return int(int(exif.get('ImageWidth', 0)) * percent / 100)


@pass_context
def vh(context, percent):
    exif = context.get('exif', {})
    return int(int(exif.get('ImageHeight', 0)) * percent / 100)


@pass_context
def auto_logo(context, brand: str | None = None):
    exif = context.get('exif', {})
    brand = (brand or exif.get('Make', 'default')).lower()

    # 1. 优先匹配用户自定义 Logo
    custom_dir = logos_dir / "custom"
    if custom_dir.exists():
        for f in custom_dir.iterdir():
            if f.suffix.lower() in {'.png', '.jpg', '.jpeg'} and f.stem.lower() in brand:
                return str(f.absolute()).replace('\\', '/')

    # 2. 回退到内置默认 Logo
    for f in logos_dir.iterdir():
        if f.is_file() and f.suffix.lower() in {'.png', '.jpg', '.jpeg'} and f.stem.lower() in brand:
            return str(f.absolute()).replace('\\', '/')
    return None
