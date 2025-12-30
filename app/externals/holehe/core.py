import importlib
import os
import pkgutil
import re
import time
from subprocess import PIPE, Popen

import httpx
import trio

from app.externals.holehe.instruments import TrioProgress

DEBUG = False
EMAIL_FORMAT = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

__version__ = "1.61"


def import_submodules(package, recursive=True):
    """Get all the holehe submodules"""
    if isinstance(package, str):
        package = importlib.import_module(package)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name
        results[full_name] = importlib.import_module(full_name)
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results


def get_functions(modules, args=None):
    """Transform the modules objects to functions"""
    websites = []

    for module in modules:

        if len(module.split(".")) > 5:

            modu = modules[module]
            site = module.split(".")[-1]
            if args is not None:
                if (
                    "adobe" not in str(modu.__dict__[site])
                    and "mail_ru" not in str(modu.__dict__[site])
                    and "odnoklassniki" not in str(modu.__dict__[site])
                    and "samsung" not in str(modu.__dict__[site])
                ):
                    websites.append(modu.__dict__[site])
            else:
                websites.append(modu.__dict__[site])
    return websites


def check_update():
    """Check and update holehe if not the last version"""
    check_version = httpx.get("https://pypi.org/pypi/holehe/json")
    if check_version.json()["info"]["version"] != __version__:
        if os.name != "nt":
            p = Popen(
                ["pip3", "install", "--upgrade", "holehe"], stdout=PIPE, stderr=PIPE
            )
        else:
            p = Popen(
                ["pip", "install", "--upgrade", "holehe"], stdout=PIPE, stderr=PIPE
            )
        (output, err) = p.communicate()
        p_status = p.wait()
        print("Holehe has just been updated, you can restart it.")
        exit()


def is_email(email: str) -> bool:
    """Check if the input is a valid email address

    Keyword Arguments:
    email       -- String to be tested

    Return Value:
    Boolean     -- True if string is an email, False otherwise
    """

    return bool(re.fullmatch(EMAIL_FORMAT, email))


def print_result(data, email, websites):
    websiteprint = []
    for results in data:
        if results["exists"] == True:
            toprint = ""
            if results["emailrecovery"] is not None:
                toprint += " " + results["emailrecovery"]
            if results["phoneNumber"] is not None:
                toprint += " / " + results["phoneNumber"]
            if results["others"] is not None and "FullName" in str(
                results["others"].keys()
            ):
                toprint += " / FullName " + results["others"]["FullName"]
            if results["others"] is not None and "Date, time of the creation" in str(
                results["others"].keys()
            ):
                toprint += (
                    " / Date, time of the creation "
                    + results["others"]["Date, time of the creation"]
                )

            websiteprint = websiteprint + [results["domain"] + toprint]

    return websiteprint


async def launch_module(module, email, client, out):
    data = {
        "aboutme": "about.me",
        "adobe": "adobe.com",
        "amazon": "amazon.in",
        "anydo": "any.do",
        "archive": "archive.org",
        "armurerieauxerre": "armurerie-auxerre.com",
        "atlassian": "atlassian.com",
        "babeshows": "babeshows.co.uk",
        "badeggsonline": "badeggsonline.com",
        "biosmods": "bios-mods.com",
        "biotechnologyforums": "biotechnologyforums.com",
        "bitmoji": "bitmoji.com",
        "blablacar": "blablacar.com",
        "blackworldforum": "blackworldforum.com",
        "blip": "blip.fm",
        "blitzortung": "forum.blitzortung.org",
        "bluegrassrivals": "bluegrassrivals.com",
        "bodybuilding": "bodybuilding.com",
        "buymeacoffee": "buymeacoffee.com",
        "cambridgemt": "discussion.cambridge-mt.com",
        "caringbridge": "caringbridge.org",
        "chinaphonearena": "chinaphonearena.com",
        "clashfarmer": "clashfarmer.com",
        "codecademy": "codecademy.com",
        "codeigniter": "forum.codeigniter.com",
        "codepen": "codepen.io",
        "coroflot": "coroflot.com",
        "cpaelites": "cpaelites.com",
        "cpahero": "cpahero.com",
        "cracked_to": "cracked.to",
        "crevado": "crevado.com",
        "deliveroo": "deliveroo.com",
        "demonforums": "demonforums.net",
        "devrant": "devrant.com",
        "diigo": "diigo.com",
        "discord": "discord.com",
        "docker": "docker.com",
        "dominosfr": "dominos.fr",
        "ebay": "ebay.com",
        "ello": "ello.co",
        "envato": "envato.com",
        "eventbrite": "eventbrite.com",
        "evernote": "evernote.com",
        "fanpop": "fanpop.com",
        "firefox": "firefox.com",
        "flickr": "flickr.com",
        "freelancer": "freelancer.com",
        "freiberg": "drachenhort.user.stunet.tu-freiberg.de",
        "garmin": "garmin.com",
        "github": "github.com",
        "google": "google.com",
        "gravatar": "gravatar.com",
        "imgur": "imgur.com",
        "instagram": "instagram.com",
        "issuu": "issuu.com",
        "koditv": "forum.kodi.tv",
        "komoot": "komoot.com",
        "laposte": "laposte.fr",
        "lastfm": "last.fm",
        "lastpass": "lastpass.com",
        "mail_ru": "mail.ru",
        "mybb": "community.mybb.com",
        "myspace": "myspace.com",
        "nattyornot": "nattyornotforum.nattyornot.com",
        "naturabuy": "naturabuy.fr",
        "ndemiccreations": "forum.ndemiccreations.com",
        "nextpvr": "forums.nextpvr.com",
        "nike": "nike.com",
        "odnoklassniki": "ok.ru",
        "office365": "office365.com",
        "onlinesequencer": "onlinesequencer.net",
        "parler": "parler.com",
        "patreon": "patreon.com",
        "pinterest": "pinterest.com",
        "plurk": "plurk.com",
        "pornhub": "pornhub.com",
        "protonmail": "protonmail.ch",
        "quora": "quora.com",
        "rambler": "rambler.ru",
        "redtube": "redtube.com",
        "replit": "replit.com",
        "rocketreach": "rocketreach.co",
        "samsung": "samsung.com",
        "seoclerks": "seoclerks.com",
        "sevencups": "7cups.com",
        "smule": "smule.com",
        "snapchat": "snapchat.com",
        "soundcloud": "soundcloud.com",
        "sporcle": "sporcle.com",
        "spotify": "spotify.com",
        "strava": "strava.com",
        "taringa": "taringa.net",
        "teamtreehouse": "teamtreehouse.com",
        "tellonym": "tellonym.me",
        "thecardboard": "thecardboard.org",
        "therianguide": "forums.therian-guide.com",
        "thevapingforum": "thevapingforum.com",
        "tumblr": "tumblr.com",
        "tunefind": "tunefind.com",
        "twitter": "twitter.com",
        "venmo": "venmo.com",
        "vivino": "vivino.com",
        "voxmedia": "voxmedia.com",
        "vrbo": "vrbo.com",
        "vsco": "vsco.co",
        "wattpad": "wattpad.com",
        "xing": "xing.com",
        "xnxx": "xnxx.com",
        "xvideos": "xvideos.com",
        "yahoo": "yahoo.com",
        "hubspot": "hubspot.com",
        "pipedrive": "pipedrive.com",
        "insightly": "insightly.com",
        "nutshell": "nutshell.com",
        "zoho": "zoho.com",
        "axonaut": "axonaut.com",
        "amocrm": "amocrm.com",
        "nimble": "nimble.com",
        "nocrm": "nocrm.io",
        "teamleader": "teamleader.eu",
    }
    try:
        await module(email, client, out)
    except Exception:
        # Safely extract module name and domain, handling any parsing errors
        try:
            name = str(module).split("<function ")[1].split(" ")[0]
        except Exception:
            name = "unknown"
        try:
            domain = data.get(name, "unknown.com")
        except Exception:
            domain = "unknown.com"
        out.append(
            {
                "name": name,
                "domain": domain,
                "rateLimit": True,
                "exists": False,
                "emailrecovery": None,
                "phoneNumber": None,
                "others": None,
            }
        )


async def maincore(email):

    if not is_email(email):
        exit("[-] Please enter a target email !")

    # Import Modules
    modules = import_submodules("app.externals.holehe.modules")

    websites = get_functions(modules)

    timeout = 10
    # Start time
    start_time = time.time()
    # Def the async client
    client = httpx.AsyncClient(timeout=timeout)

    # Launching the modules
    out = []
    instrument = TrioProgress(len(websites))

    trio.lowlevel.add_instrument(instrument)
    async with trio.open_nursery() as nursery:
        for website in websites:
            nursery.start_soon(launch_module, website, email, client, out)
    trio.lowlevel.remove_instrument(instrument)
    # Sort by modules names
    out = sorted(out, key=lambda i: i["name"])
    # Close the client
    await client.aclose()
    # Print the result
    website_result = print_result(out, email, websites)

    return website_result


def main(email):
    website_result = trio.run(maincore, email)
    return website_result
