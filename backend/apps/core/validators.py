from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


@deconstructible
class FileValidator:
    def __init__(self, allowed_types, max_size):
        self.allowed_types = allowed_types
        self.max_size = max_size

    def __call__(self, file):
        content_type = getattr(file, "content_type", None)
        if content_type and content_type not in self.allowed_types:
            raise ValidationError(f"Unsupported file type: {content_type}.")
        size = getattr(file, "size", 0)
        if size > self.max_size:
            raise ValidationError(
                f"File is too large ({round(size / 1024 / 1024, 1)} MB). "
                f"Maximum is {self.max_size // (1024 * 1024)} MB."
            )
        name = (getattr(file, "name", "") or "").lower()
        dangerous = (".php", ".exe", ".sh", ".bat", ".js", ".html", ".svg")
        if name.endswith(dangerous):
            raise ValidationError("This file extension is not allowed.")


validate_image_upload = FileValidator(ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE)
validate_document_upload = FileValidator(ALLOWED_DOCUMENT_TYPES, MAX_DOCUMENT_SIZE)
