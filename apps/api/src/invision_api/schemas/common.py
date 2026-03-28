from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(..., examples=["validation_error"])
    message: str


class MessageResponse(BaseModel):
    message: str
