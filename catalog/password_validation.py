from django.contrib.auth.password_validation import MinimumLengthValidator
from django.utils.translation import get_language


class VietnameseMinimumLengthValidator(MinimumLengthValidator):
    def get_error_message(self):
        if get_language() == "vi":
            return self.get_help_text()
        return super().get_error_message()
