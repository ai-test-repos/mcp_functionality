import google.generativeai as genai

# --- Configuration ---
# Replace with your actual API key
# You can obtain an API key from Google's AI Studio:
# https://aistudio.google.com/app/apikey
GEMINI_API_KEY = "AIzaSyAmnu-l-C5mDGyK16SHCvJSykoazlhBXUE"

# --- Tool Definitions ---

def add(a: int, b: int) -> int:
    """Adds two integers together."""
    return a + b

def subtract(a: int, b: int) -> int:
    """Subtracts the second integer from the first."""
    return a - b

def multiply(a: int, b: int) -> int:
    """Multiplies two integers."""
    return a * b

def main():
    """
    A simple client to demonstrate function calling with the Gemini API.
    """

    # --- Initialize the Gemini Model ---
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[add, subtract, multiply]
    )
    chat = model.start_chat()

    # --- Interact with the Model ---
    prompts = [
        "What is the sum of 15 and 27?",
        "Can you subtract 10 from 33?",
        "What do you get when you multiply 8 by 9?",
    ]

    for prompt in prompts:
        print(f"User: {prompt}")
        response = chat.send_message(prompt)

        # Check for function calls
        if response.function_call:
            for function_call in response.function_calls:
                # Find the corresponding function
                tool = globals()[function_call.name]

                # Call the function with the provided arguments
                result = tool(**function_call.args)

                # Send the function's result back to the model
                response = chat.send_message(
                    part=genai.Part(
                        function_response=genai.FunctionResponse(
                            name=function_call.name,
                            response={"result": result},
                        )
                    )
                )

        print(f"Gemini: {response.text}\n")


if __name__ == "__main__":
    main()