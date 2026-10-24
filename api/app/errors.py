from fastapi import HTTPException


class Cancelled(Exception):
    """Raised inside a background job when the user cancelled it, or a run was paused."""


ERROR_MESSAGES = {
    # Vision model.
    "vision_model_not_set": "No vision model is selected yet.",
    "vision_model_missing": "The selected vision model is not installed.",
    "vision_unreachable": "The local AI engine is not running.",
    "vision_timeout": "The model took too long on this screenshot.",
    "vision_failed": "The model returned an error. Try again.",
    "invalid_model_output": "The model's answer could not be understood, even after a retry.",
    "model_has_no_vision": (
        "This model cannot read images. Choose one of the recommended vision models."
    ),
    # Images.
    "unsupported_file_type": "That file is not an image Slothshot can read.",
    "image_unreadable": "The image could not be opened. It may be damaged.",
    "file_empty": "The file is empty.",
    # Ollama / downloads, shared with the first-launch wizard.
    "ollama_unreachable": "The local AI engine is not running.",
    "ollama_failed": "The local AI engine returned an error. Try again.",
    "model_not_found": "No model with that name exists in the Ollama library. Check name and tag.",
    "invalid_model_name": "That is not a valid model name. Use name:tag, for example gemma4:e2b.",
    "cloud_model": (
        "Cloud models send your screenshots to a server. "
        "Slothshot only uses models that run on this computer."
    ),
    "network_error": (
        "The download stopped because the network connection was lost. "
        "Try again: it continues where it left off."
    ),
    "download_failed": "The download server did not send the expected file. Try again later.",
    "pull_failed": "The model could not be downloaded. Try again.",
    "not_enough_disk": "There is not enough free disk space for this download.",
    "model_not_installed": "That model is not on this computer.",
    "setup_failed": "Something went wrong during setup. Try again.",
    "setup_busy": "A download is already in progress.",
    "nothing_to_resume": "There is no interrupted download to resume.",
    "compat_needed": "This model has not been checked on this computer yet.",
    "model_in_use": "This is the model in use. Switch to another model first.",
    "compat_no_vision": (
        "This model could not read a test image. It is probably not a vision model."
    ),
    "compat_invalid_output": (
        "This model did not return the structured answer the app needs, even after a retry."
    ),
    "compat_timeout": (
        "This model took too long on a small test image. It may be too big for this computer."
    ),
    "compat_model_missing": "The model disappeared before it could be tested. Try again.",
    # Folders.
    "folder_not_found": "That folder does not exist.",
    "not_a_folder": "That path is not a folder.",
    "folder_unreadable": "Slothshot is not allowed to read that folder.",
    "folder_already_watched": "That folder is already on the list.",
    "folder_inside_watched": "That folder is already covered by one on the list.",
    "cannot_watch_organized": "That is a folder Slothshot created. Pick the folder above it.",
    # Runs.
    "run_not_found": "Run not found.",
    "run_in_progress": "A run is already going.",
    "no_run_in_progress": "There is no run to stop.",
    "nothing_to_organize": "There is nothing waiting to be organized.",
    "approval_required": "This run is waiting for you to approve the preview.",
    "already_approved": "This run has already been approved.",
    # Undo.
    "nothing_to_undo": "There is nothing to undo.",
    "already_undone": "That change has already been undone.",
    "undo_blocked_missing": (
        "That file is not where Slothshot left it, so it cannot be put back. Nothing was changed."
    ),
    "undo_blocked_occupied": (
        "Something else now sits where that file came from, so it cannot be put back. "
        "Nothing was changed."
    ),
    # Screenshots.
    "screenshot_not_found": "Screenshot not found.",
    "text_not_indexed": (
        "This screenshot is marked sensitive, so its text was never stored. "
        "Turn on indexing of sensitive text to search it."
    ),
}


class ApiError(HTTPException):
    """A refused request. `code` is stable and `params` fill in its message, so the web app can
    show it in its own words; the English text (`detail`) stays for anything that does not know
    the code."""

    def __init__(
        self, status_code: int, code: str, message: str | None = None, **params: object
    ) -> None:
        super().__init__(status_code, message if message is not None else ERROR_MESSAGES[code])
        self.code = code
        self.params = params
