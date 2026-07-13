from dataclasses import dataclass


@dataclass
class FitError(Exception):
    code: str
    path: list[str | int]
    message: str
    required_mm: dict[str, float] | None = None
    available_mm: dict[str, float] | None = None

    def detail(self):
        result = {"code": self.code, "path": self.path, "message": self.message}
        if self.required_mm is not None:
            result["required_mm"] = self.required_mm
        if self.available_mm is not None:
            result["available_mm"] = self.available_mm
        return result
