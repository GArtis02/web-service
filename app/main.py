from fastapi import FastAPI
from pydantic import BaseModel
import app.creds as creds
import openai
import random
import time

app = FastAPI()

# add key
openai.api_key = 


# Model for a single message
class Message(BaseModel):
    role: str
    content: str


# Define the tool functions
def return_string():
    return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5))


def return_integer():
    return random.randint(0, 9)


def return_pokemon():
    # Dummy Pokemon weakness tool - in a real case, this would return correct weakness types.
    return "Venusaur is weak to Flying, Psychic, Ice, and Fire types."


# Define the custom tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "return_string",
            "description": "Returns a random text string",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "return_integer",
            "description": "Returns an integer from 0 to 9",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "return_pokemon",
            "description": "Returns the types a Pokemon is weak to",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# 40-mini is the cheapest one.
assistant = openai.beta.assistants.create(
    name="Custom Tool Assistant",
    instructions="You are an assistant with access to custom tools that return random strings, integers, pokemon weakness.",
    model="gpt-4o-mini",
    tools=tools
)

# Route to receive and process a user message
@app.post("/send-message/")
async def process_message_and_respond(thread_id: str, message: str):
    """
    Receive a message from the user and return a response from the virtual assistant.

    Args:
        thread_id (str): The ID of the conversation thread.
        message (str): The message sent by the user.

    Returns:
        dict: A dictionary containing the thread ID, the assistant's response, and the original message.
    """
    
    # Create a new thread for the conversation if not already present
    thread = openai.beta.threads.create()
    
    # Add the received message to the conversation thread
    user_message = openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message
    )
    
    # Run the assistant
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )
    
    # Poll for the assistant's response
    attempt = 1
    while run.status != "completed":
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "requires_action":
            break
        attempt += 1
        time.sleep(2)
    
    # If the assistant requests to use a tool
    if run.status == "requires_action":
        if run.required_action:
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                if tool_call.function.name == "return_string":
                    output = return_string()
                elif tool_call.function.name == "return_integer":
                    output = return_integer()
                elif tool_call.function.name == "return_pokemon":
                    output = return_pokemon()
                else:
                    output = "Unknown tool"
                
                # Submit the tool's result back to the assistant
                openai.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=[{
                        "tool_call_id": tool_call.id,
                        "output": str(output)
                    }]
                )
    
    # Wait for the assistant to complete the run after using the tool
    run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    attempt = 1
    while run.status not in ["completed", "failed"]:
        time.sleep(2)
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        attempt += 1
    
    # Retrieve the assistant's final response
    if run.status == "completed":
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        final_answer = messages.data[0].content[0].text.value
        return {
            "thread_id": thread_id,
            "response": final_answer,
            "message_received": message
        }
    else:
        return {
            "thread_id": thread_id,
            "response": "The assistant failed to complete the request.",
            "message_received": message
        }


# Retrieve a conversation history based on the thread ID, 5 messages from the user, 5 from the assistant
@app.get("/conversation-history/")
async def conversation_history(thread_id: str):
    """
    Retrieve the conversation history for a specific thread.

    Args:
        thread_id (str): The ID of the conversation thread.

    Returns:
        dict: A dictionary containing the thread ID and a list of conversation messages, including both user and assistant messages.
    """
    
    # Fill the message history with dummy messages
    user_messages = [f"User message {i} in thread {thread_id}" for i in range(1, 6)]
    assistant_messages = [f"Assistant message {i} in thread {thread_id}" for i in range(1, 6)]
    conversation_history = []
    for i in range(5):
        conversation_history.append({"sender": "user", "content": user_messages[i]})
        conversation_history.append({"sender": "assistant", "content": assistant_messages[i]})

    return {
        "thread_id": thread_id,
        "conversation_history": conversation_history
    }
