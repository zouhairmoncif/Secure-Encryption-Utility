"""Decrypt workflow page."""

from .transform_page import FileOperationPage


class DecryptPage(FileOperationPage):
    MODE = "decrypt"
    ACTION_VERB = "Decrypt"
    ACTION_PAST = "decrypted"
    ACTION_ICON = "unlock"
    RESULT_ICON = "checkCircle"