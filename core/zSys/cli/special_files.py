import sys
from pathlib import Path

def detect_special_files(parser, logger, argv=None, cwd=None):
    """Detect Python (.py) files or zSpark (.zolo) files in arguments."""
    argv = sys.argv[1:] if argv is None else list(argv)
    cwd = Path.cwd() if cwd is None else cwd

    positional_args = [arg for arg in argv if not arg.startswith('-')]

    if not positional_args:
        return None, None, parser.parse_args(argv)

    first_arg = positional_args[0]

    # Remove only the first occurrence of first_arg from argv
    filtered_argv = list(argv)
    filtered_argv.remove(first_arg)

    # Python script execution
    if first_arg.endswith('.py'):
        logger.debug("Detected Python script: %s", first_arg)
        return first_arg, None, parser.parse_args(filtered_argv)

    # zSpark.*.zolo execution — three forms accepted:
    #   z hangman                          → zSpark.hangman.zolo in cwd
    #   z zSpark.hangman.zolo              → relative path in cwd
    #   z /abs/path/to/zSpark.hangman.zolo → absolute path (e.g. from Finder launcher)
    if first_arg.endswith('.zolo'):
        zspark_path = Path(first_arg)
        if not zspark_path.is_absolute():
            zspark_path = cwd / zspark_path
        if zspark_path.exists():
            logger.debug("Detected zSpark file: %s", zspark_path)
            return None, str(zspark_path), parser.parse_args(filtered_argv)

    if '.' not in first_arg:
        potential_zspark = cwd / f"zSpark.{first_arg}.zolo"
        if potential_zspark.exists():
            logger.debug("Detected zSpark file: %s", potential_zspark)
            return None, str(potential_zspark), parser.parse_args(filtered_argv)

    return None, None, parser.parse_args(argv)
