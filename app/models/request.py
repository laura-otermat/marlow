from pydantic import BaseModel


class RememberRequest(BaseModel):
    message: str
    household_id: str

