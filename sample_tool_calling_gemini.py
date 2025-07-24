import asyncio
from  google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import os
from dotenv import load_dotenv

"""Function definitions"""
def add(a: float, b: float):
    """returns a + b."""
    return a + b

async def call_fall_detection_mcp():
    print("Calling fall detection mcp")
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool("handle_fall_detection", {})
            return response

# Paramerter schema created
math_params = {
    "type": "object",
    "properties": {
        "a": {"type": "number", "description": "First number"},
        "b": {"type": "number", "description": "Second number"},
    },
    "required": ["a", "b"],
}
# Declare math functions as Gemini tools
tool = types.Tool(function_declarations=[
    types.FunctionDeclaration(name="add", description="Adds two numbers", parameters=math_params),
    types.FunctionDeclaration(
        name="call_fall_detection_mcp",
        description="Calls fall detection service.",
    )
])


load_dotenv()





async def main():
    # Load system prompt
    with open('config.txt', 'r') as fp:
        system_instruction = fp.read()

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    chat = client.chats.create(
    model= 'gemini-2.5-flash',
    config={
        "tools": [tool],
        "system_instruction": system_instruction,
        "automatic_function_calling": {"disable": False} # Enabled by default
    }
)

    # Send a user message
    response = chat.send_message("Check fall detection")

    part = response.candidates[0].content.parts[0]

    # Check for function call
    if hasattr(part, "function_call"):
        fn_call = part.function_call
        fn_name = fn_call.name
        fn_args = fn_call.args

        print(f"Gemini wants to call: {fn_name} with args: {fn_args}")

        if fn_name == "call_fall_detection_mcp":
            result = await call_fall_detection_mcp()
            print("Fall detection result:", result)
        else:
            print("Function not recognized.")
    else:
        print("Gemini response:", response.text)

# -------------------------------
# Entry point
# -------------------------------

if __name__ == "__main__":
    asyncio.run(main())