import re

from discord.app_commands import CommandInvokeError


def generate_generic_error_message(exception: Exception):
    cause = (
        exception.original.__class__.__name__
        if isinstance(exception, CommandInvokeError)
        else exception.__class__.__name__
    )
    error_code = "_".join(
        re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", cause),
    ).upper()
    return "\n".join(
        [
            "Something went wrong handling your request.",
            f"-# This incident has been recorded; {error_code}",
        ],
    )
