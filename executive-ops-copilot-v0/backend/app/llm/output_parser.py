from pydantic import BaseModel, ValidationError


class InvalidLLMOutput(ValueError):
    pass


def parse_llm_output(output: dict, schema: type[BaseModel]) -> BaseModel:
    try:
        return schema.model_validate(output)
    except ValidationError as exc:
        raise InvalidLLMOutput(str(exc)) from exc
