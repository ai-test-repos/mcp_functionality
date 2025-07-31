# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
## Setup

To install the dependencies for this script, run:

```
pip install -U google-genai pyaudio keyboard
```

## API key

Ensure the `GOOGLE_API_KEY` environment variable is set to the api-key
you obtained from Google AI Studio.

## Run

To run the script:

```
python Get_started_LiveAPI_NativeAudio_with_mute.py
```

Start talking to Gemini. Press 'm' to mute the microphone, 'u' to unmute.
"""
import os
import asyncio
import sys
import traceback
import threading
import pyaudio
import keyboard
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
import logging
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
load_dotenv()


if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()




LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "audio_loop.log")

logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',  # append mode
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL = "gemini-2.5-flash-preview-native-audio-dialog"

with open('config.txt', 'r') as fp:
    system_instruction = fp.read()

async def call_fall_detection_mcp():
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("handle_fall_detection", {})
            logging.info(f"[Fall Detection Result] result")
            return result

async def call_check_vitals_mcp():
    url = "http://localhost:8000/mcp"  # MCP server endpoint

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            logging.info("Calling tool: check_vitals")
            result = await session.call_tool("check_vitals", {})

            logging.info(f"[Vitals Result] {result}")
            return result

async def call_read_label_mcp():
    url = "http://localhost:8000/mcp"

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            logging.info("Calling tool: read_label")
            result = await session.call_tool("read_label", {"image1_path":'C:\\Users\\nidhi.ARORNI\\gemini_client_mcp_server\\Images\\image1.jpeg',
                                             "image2_path":'C:\\Users\\nidhi.ARORNI\\gemini_client_mcp_server\\Images\\image2.jpeg'})

            logging.info(f"[read_label results are: ] {result}")
            return result

# Declare functions as Gemini tools
tools = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="call_fall_detection_mcp",
        description="Check if the fall has happened.",
        parameters={"type": "object", "properties": {}, "required":[]}
    ),
    types.FunctionDeclaration(
        name="call_check_vitals_mcp",
        description="Connect with mcp server to get the vitals",
        parameters={"type": "object", "properties": {}, "required": []}
    ),
    types.FunctionDeclaration(
        name="call_read_label_mcp",
        description="Reads labels from the two image files given in the call_read_label_mcp function",
        parameters={"type": "object", "properties": {}}
    )
])

CONFIG = {"response_modalities": ["AUDIO"], "system_instruction": system_instruction,"tools": [tools]}


class AudioLoop:
    def __init__(self):
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.muted = False
        self._keyboard_thread = None
        self._stop_keyboard = threading.Event()

    def start_keyboard_listener(self):
        def listen_keys():
            print("Press 'm' to mute, 'u' to unmute the microphone.")
            while not self._stop_keyboard.is_set():
                if keyboard.is_pressed('m'):
                    if not self.muted:
                        self.muted = True
                        print("[Microphone muted]")
                        logging.info("[Microphone muted]")
                    # Debounce
                    while keyboard.is_pressed('m'):
                        if self._stop_keyboard.is_set():
                            return
                        pass
                if keyboard.is_pressed('u'):
                    if self.muted:
                        self.muted = False
                        print("[Microphone unmuted]")
                    # Debounce
                    while keyboard.is_pressed('u'):
                        if self._stop_keyboard.is_set():
                            return
                        pass
                # Sleep a little to avoid busy loop
                time.sleep(0.05)

        self._keyboard_thread = threading.Thread(target=listen_keys, daemon=True)
        self._keyboard_thread.start()

    def stop_keyboard_listener(self):
        self._stop_keyboard.set()
        if self._keyboard_thread:
            self._keyboard_thread.join()

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            if self.muted:
                await asyncio.sleep(0.05)  # Don't send anything while muted
                continue
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        """Background task to read from the websocket and write pcm chunks to the output queue"""
        logging.info("In receive audio function")

        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue

                if text := response.text:
                    print(text, end="")
                    logging.info(f"Text received: {text}")

                #to handle tool calling
                if response.tool_call:
                    tool_responses = []
                    for fun_call in response.tool_call.function_calls:
                        fn_name = fun_call.name
                        if fn_name == "call_read_label_mcp":
                            logging.info("\n[Gemini triggered read label mcp tool]\n")
                            result = await call_read_label_mcp()
                            structured_result = result.structuredContent  # extract dict
                            logging.info(f"Structured result from read label service: {structured_result}")

                            function_response = types.FunctionResponse(
                                id=fun_call.id,
                                name=fn_name,
                                response=structured_result
                            )
                            tool_responses.append(function_response)
                        elif fn_name == "call_check_vitals_mcp":
                            logging.info("\n[Gemini triggered vital service]\n")
                            result = await call_check_vitals_mcp()
                            structured_result = result.structuredContent  # extract dict
                            logging.info(f"Structured result from fall detection service: {structured_result}")

                            function_response = types.FunctionResponse(
                                id=fun_call.id,
                                name=fn_name,
                                response=structured_result
                            )
                            tool_responses.append(function_response)
                        else:
                            logging.warning(f"Unhandled function call: {fn_name}")

                    # Send tool responses back to Gemini
                    if tool_responses:
                        await self.session.send_tool_response(function_responses=tool_responses)
                        logging.info("Tool response sent to Gemini.")

            # Drain the audio queue to avoid leftover audio
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            self.start_keyboard_listener()
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            if self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG)
        finally:
            self.stop_keyboard_listener()


if __name__ == "__main__":
    loop = AudioLoop()
    asyncio.run(loop.run())

