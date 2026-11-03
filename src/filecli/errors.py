"""Shared operation error types."""


class OperationError(Exception):
    """An operation was rejected or could not be completed safely."""


class ConflictError(OperationError):
    """The destination already exists and must be resolved explicitly."""

