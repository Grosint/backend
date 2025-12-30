import configparser
from collections import namedtuple
from pathlib import Path

import httpx

endpoint_config = configparser.ConfigParser()
philint_root = Path(__file__).parent.parent.parent
endpoint_config.read(str(philint_root / "endpoints.conf"))

WordPressData = namedtuple("WordPress", ["Has_account"])


async def from_email(email):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            endpoint_config["WordPress"]["ENDPOINT_EMAIL"] + email + "/auth-options",
            headers={"User-Agent": endpoint_config["BASE"]["USER_AGENT"]},
        )
    response = resp.json()
    if "message" in response and response["message"] == "User does not exist.":
        return None
    print("WordPress : found 1 user.")
    return WordPressData(Has_account=True)
