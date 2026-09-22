"""Encrypt workflow page."""

from .transform_page import FileOperationPage


class EncryptPage(FileOperationPage):
    MODE = "encrypt"
    ACTION_VERB = "Encrypt"
    ACTION_PAST = "encrypted"
    ACTION_ICON = "lock"
    RESULT_ICON = "checkCircle"