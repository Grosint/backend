import configparser
from collections import namedtuple
from pathlib import Path

import httpx

endpoint_config = configparser.ConfigParser()
philint_root = Path(__file__).parent.parent.parent
endpoint_config.read(str(philint_root / "endpoints.conf"))

TwitterData = namedtuple("Twitter", ["Has_account"])


async def from_email(email):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            endpoint_config["Twitter"]["ENDPOINT_EMAIL"] + email,
            headers={"User-Agent": endpoint_config["BASE"]["USER_AGENT"]},
        )
    response = resp.json()
    if response["taken"]:
        print("Twitter : found 1 user.")
        return TwitterData(Has_account=True)
    return None
