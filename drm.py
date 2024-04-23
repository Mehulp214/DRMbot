from pyrogram import Client, filters
import asyncio
import shlex
import os
from os.path import join
from aiofiles.os import remove
import pytz
import datetime
from aiohttp import ClientSession
import argparse

# Initialize the Pyrogram client
#app = Client("6736865642:AAFxmkIWGgDtteisEEirpdptr6FiZn_4ZnI")

# Logger configuration
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# Helper functions
async def __subprocess_call(cmd):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return False, stderr.decode()
    return True, None

async def download_video(mpd_link, name, resl):
    class SERVICE:

        def __init__(self):
            self._remoteapi = "https://app.magmail.eu.org/get_keys"

        @staticmethod
        def c_name(name: str) -> str:
            for i in ["/", ":", "{", "}", "|"]:
                name = name.replace(i, "_")
            return name

        def get_date(self) -> str:
            tz = pytz.timezone('Asia/Kolkata')
            ct = datetime.datetime.now(tz)
            return ct.strftime("%d %b %Y - %I:%M%p")

        async def get_keys(self):
            async with ClientSession(headers={"user-agent": "okhttp"}) as session:
                async with session.post(self._remoteapi,
                                        json={"link": self.mpd_link}) as resp:
                    if resp.status != 200:
                        LOGGER.error(f"Invalid request: {await resp.text()}")
                        return None
                    response = await resp.json(content_type=None)
            self.mpd_link = response["MPD"]
            return response["KEY_STRING"]


    class Download(SERVICE):

        def __init__(self, name: str, resl: str, mpd: str):
            super().__init__()
            self.mpd_link = mpd
            self.name = self.c_name(name)
            self.vid_format = f'bestvideo.{resl}/bestvideo.2/bestvideo'

            videos_dir = "Videos"
            encrypted_basename = f"{self.name}_enc"
            decrypted_basename = f"{self.name}_dec"

            self.encrypted_video = join(videos_dir, f"{encrypted_basename}.mp4")
            self.encrypted_audio = join(videos_dir, f"{encrypted_basename}.m4a")
            self.decrypted_video = join(videos_dir, f"{decrypted_basename}.mp4")
            self.decrypted_audio = join(videos_dir, f"{decrypted_basename}.m4a")
            self.merged = join(videos_dir, f"{self.name} - {self.get_date()}.mkv")

        async def process_video(self):
            key = await self.get_keys()
            if not key:
                LOGGER.error("Could not retrieve decryption keys.")
                return
            LOGGER.info(f"MPD: {self.mpd_link}")
            LOGGER.info(f"Got the Keys > {key}")
            LOGGER.info(f"Downloading Started...")
            if await self.__yt_dlp_drm() and await self.__decrypt(
                    key) and await self.__merge():
                LOGGER.info(f"Cleaning up files for: {self.name}")
                await self.__cleanup_files()
                LOGGER.info(f"Downloading complete for: {self.name}")
                return self.merged
            LOGGER.error(f"Processing failed for: {self.name}")
            return None

        async def __subprocess_call(self, cmd):
            if isinstance(cmd, str):
                cmd = shlex.split(cmd)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                LOGGER.error(
                    f"Command failed: {' '.join(cmd)}\nError: {stderr.decode()}")
                return False
            return True

        async def __yt_dlp_drm(self):
            video_download = await self.__subprocess_call(
                f'yt-dlp -k --allow-unplayable-formats -f "{self.vid_format}" --fixup never "{self.mpd_link}" --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M" -o "{self.encrypted_video}"'
            )
            audio_download = await self.__subprocess_call(
                f'yt-dlp -k --allow-unplayable-formats -f ba --fixup never "{self.mpd_link}" --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M" -o "{self.encrypted_audio}"'
            )
            return video_download and audio_download

        async def __decrypt(self, key):
            LOGGER.info("Decrypting...")
            video_decrypt = await self.__subprocess_call(
                f'mp4decrypt --show-progress {key} "{self.encrypted_video}" "{self.decrypted_video}"'
            )
            audio_decrypt = await self.__subprocess_call(
                f'mp4decrypt --show-progress {key} "{self.encrypted_audio}" "{self.decrypted_audio}"'
            )
            return video_decrypt and audio_decrypt

        async def __merge(self):
            LOGGER.info("Merging...")
            return await self.__subprocess_call(
                f'ffmpeg -i "{self.decrypted_video}" -i "{self.decrypted_audio}" -c copy "{self.merged}"'
            )

        async def __cleanup_files(self):
            for file_path in [
                    self.encrypted_video, self.encrypted_audio,
                    self.decrypted_audio, self.decrypted_video
            ]:
                try:
                    await remove(file_path)
                except Exception as e:
                    LOGGER.warning(f"Failed to delete {file_path}: {str(e)}")

    downloader = Download(name, resl, mpd_link)
    return await downloader.process_video()


# Define handlers for commands or messages
@app.on_message(filters.command(["start"]))
async def start_command(client, message):
    await message.reply("Send me the MPD link of the video.")

@app.on_message(filters.text & ~filters.command(["start"]))
async def process_video(client, message):
    mpd_link = message.text
    name = "output"
    resl = "1"
    await message.reply("Downloading and processing the video...")
    result = await download_video(mpd_link, name, resl)
    if result:
        await message.reply_video(result, caption="Video processed successfully!")
    else:
        await message.reply("Error processing the video.")
      
app = Client(
    "my_bot",
    api_id=23476439,
    api_hash="1626e884119a29dbccbb78e39b48128f",
    bot_token="6736865642:AAFxmkIWGgDtteisEEirpdptr6FiZn_4ZnI"
)

# Run the bot
app.run()
      
