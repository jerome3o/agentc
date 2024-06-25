import os
import anthropic
from anthropic.types import ToolParam
from pydantic import BaseModel
from pathlib import Path

from c.files import read_files_with_cignore

import typer

model = os.getenv("MODEL", "claude-3-opus-20240229")

max_tokens = 1024
_system_prompt = """\
This is a conversation between a helpful AI coding assistant and a developer writing a software
project, please answer questions and use the tools available (when it makes sense) to help.

Here are the files on their machine that may be relevant:

{files}

"""


def get_system_prompt():
    return _system_prompt.format(
        files="\n".join(map(str, read_files_with_cignore(".")))
    )


class WriteFileParams(BaseModel):
    file: str
    content: str

    @classmethod
    def evaluate(cls, v: dict):
        params = cls.model_validate(v)

        acceptance = input(
            f"Write to file: {params.file}\nContent: \n{params.content}\n\nEnter to accept, otherwise write a response: "
        )

        if acceptance != "":
            return "User denied writing to file", acceptance

        with open(params.file, "w") as f:
            f.write(params.content)

        size = Path(params.file).stat().st_size

        return f"Bytes written {size}", None


class ReadFileParams(BaseModel):
    file: str

    @classmethod
    def evaluate(cls, v: dict):
        params = cls.model_validate(v)

        try:
            with open(params.file) as f:
                return f.read(), None
        except Exception as e:
            return str(e), None


tools = [
    {
        "spec": ToolParam(
            name="write_file",
            description="Write some text to a file",
            input_schema=WriteFileParams.model_json_schema(),
        ),
        "evaluator": WriteFileParams.evaluate,
    },
    {
        "spec": ToolParam(
            name="read_file",
            description="Read the contents of a file",
            input_schema=ReadFileParams.model_json_schema(),
        ),
        "evaluator": ReadFileParams.evaluate,
    },
]

tools_dict = {t["spec"]["name"]: t for t in tools}
tool_specs = [t["spec"] for t in tools]


client = anthropic.Anthropic()


def print_message(message):

    if not isinstance(message, dict):
        message = message.to_dict()

    print(_create_printable_message(message))


def _create_printable_message(message: dict) -> str:
    content = message["content"]

    if isinstance(content, str):
        return f'{message["role"]}: {message["content"]}\n'

    outputs: list[str] = []

    for block in content:
        match block["type"]:
            case "text":
                outputs.append(f'{message["role"]}: {block["text"]}')
            case "tool_result":
                outputs.append(f"tool result: {block['content']}")
            case "tool_use":
                outputs.append(f"tool request {block['name']}: {block['input']}")

    return "\n".join(outputs) + "\n"


def get_input() -> str:
    return input("> ")


def main(message: str | None = None):

    messages = [
        {
            "role": "user",
            "content": message or get_input(),
        },
    ]

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=get_system_prompt(),
        messages=messages,
        tools=tool_specs,
    )

    print_message(response)

    while True:
        if response.stop_reason == "tool_use":
            content = []
            for block in response.content:
                if block.type == "tool_use":
                    tool = tools_dict[block.name]
                    result, additional_user_message = tool["evaluator"](block.input)
                    content.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

                    if additional_user_message:
                        content.append(
                            {
                                "type": "text",
                                "text": additional_user_message,
                            }
                        )

            tool_response = {"role": "user", "content": content}
            messages.extend(
                [
                    {
                        "role": response.role,
                        "content": response.content,
                    },
                    tool_response,
                ]
            )

            print_message(tool_response)

            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=get_system_prompt(),
                messages=messages,
                tools=tool_specs,
            )

            print_message(response)

        elif response.stop_reason == "end_turn":

            user_response = {
                "role": "user",
                "content": get_input(),
            }

            messages.extend(
                [
                    {
                        "role": response.role,
                        "content": response.content,
                    },
                    user_response,
                ]
            )

            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=get_system_prompt(),
                messages=messages,
                tools=tool_specs,
            )

            print_message(response)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.WARNING)
    typer.run(main)
