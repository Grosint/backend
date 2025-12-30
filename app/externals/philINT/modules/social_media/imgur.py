import configparser
from collections import namedtuple
from pathlib import Path

import httpx

endpoint_config = configparser.ConfigParser()
philint_root = Path(__file__).parent.parent.parent
endpoint_config.read(str(philint_root / "endpoints.conf"))

ImgurData = namedtuple("Imgur", ["Has_account"])


async def from_email(email):
    headers = {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": endpoint_config["BASE"]["USER_AGENT"],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            endpoint_config["Imgur"]["ENDPOINT_EMAIL"],
            headers=headers,
            data="email=" + email,
        )
    response = resp.json()
    if "data" in response and "error" in response["data"]:
        return ImgurData(Has_account=True)
    if "data" in response and response["data"]["available"] == False:
        return ImgurData(Has_account=True)
    return None
