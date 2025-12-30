import configparser
from collections import namedtuple
from pathlib import Path

import httpx

endpoint_config = configparser.ConfigParser()
philint_root = Path(__file__).parent.parent.parent
endpoint_config.read(str(philint_root / "endpoints.conf"))

MeWeData = namedtuple("MeWe", ["Has_account"])


async def from_email(email):
    headers = {
        "accept": "application/json, text/plain, */*",
        "User-Agent": endpoint_config["BASE"]["USER_AGENT"],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            endpoint_config["MeWe"]["ENDPOINT_EMAIL"] + email, headers=headers
        )
    response = resp.json()
    if "already taken" in str(response):
        print("MeWe : found 1 user.")
        return MeWeData(Has_account=True)
    return None
