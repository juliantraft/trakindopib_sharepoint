from os import getenv
from pathlib import Path
from sys import modules
from shutil import move as sh_move


def get_env(key: str) -> str:
    """
    Wrappger for `os.getenv` function that raises
    `KeyError` if provided key does not exist.

    Args:
        key (str):

    Returns:
        str:

    Raises:
        KeyError:
    """
    value: str | None = getenv(key)

    if value is None:
        raise KeyError(f'"{key}" key not found in env')
    return value


def get_main_path() -> Path:
    """
    Returns `Path` object of the entry point file.

    Raises:
        FileNotFoundError: If `__file__` returns None.

    Returns:
        Path:
    """
    main_file: str | None = modules['__main__'].__file__

    if main_file is None:
        raise FileNotFoundError('Unable to extract __file__ from main module')
    
    return Path(main_file)
 

def move_file(filepath: Path, move_dir: Path, missing_ok: bool = False) -> None:
    """
    A general purpose move function that accepts `pathlib`'s `Path` object
    and uses `shutil.move()` to enable moving between file systems.

    Args:
        filepath (Path): `Path` of the original file.
        move_dir (Path): `Path` of the new directory.
    """
    filename: str = filepath.name

    old_path: Path = filepath.resolve()
    new_path: Path = move_dir / filename
    try:
        sh_move(str(old_path), str(new_path))
    except FileNotFoundError:
        if not missing_ok:
            raise


def move_files(files: list[Path], move_dir: Path) -> None:
    """
    General purpose bulk move function that accepts `pathlib.Path` object.
    Uses `shutil.move` to enable moving between file systems.

    Args:
        files (list[Path]): List of files.
        move_dir (Path): Destination directory.
    """
    for file in files:
        move_file(file, move_dir)