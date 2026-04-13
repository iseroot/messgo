class AppError(Exception):
    """Базовая ошибка бизнес-слоя."""


class AuthError(AppError):
    """Ошибка аутентификации."""


class PermissionDeniedError(AppError):
    """Ошибка доступа."""


class ValidationError(AppError):
    """Ошибка валидации бизнес-правил."""


class NotFoundError(AppError):
    """Сущность не найдена."""
