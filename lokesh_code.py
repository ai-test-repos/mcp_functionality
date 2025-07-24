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

To install the dependencies for this script, run:u

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

import asyncio
import sys
import traceback
import threading
import pyaudio
import keyboard
import time
from google import genai
import os

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

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
with open('config.txt','r') as fp:
    system_instruction = fp.read()

CONFIG = {"response_modalities": ["AUDIO"], "system_instruction":system_instruction}

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
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")
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