"""
Execution context logging for bootstrap diagnostics.
"""

def log_execution_context(logger, args, python_file, zspark_file):
    """Log execution context for bootstrap diagnostics."""
    verbose = getattr(args, "verbose", False)
    dev_mode = getattr(args, "dev", False)

    if zspark_file:
        exec_type = "zSpark"
    elif python_file:
        exec_type = f"python ({python_file})"
    else:
        exec_type = f"command ({getattr(args, 'command', None) or 'info'})"

    logger.debug("Execution: %s, Verbose: %s, Dev: %s", exec_type, verbose, dev_mode)
