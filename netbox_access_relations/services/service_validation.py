"""Shared validation for a policy's final service set."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_any_exclusivity(any_flags):
    flags = list(any_flags)
    if any(flags) and len(flags) > 1:
        raise ValidationError(_("ANY cannot coexist with other services in an access policy."))
