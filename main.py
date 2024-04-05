from bs4 import BeautifulSoup as BS
from bs4.element import Tag
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from time import time
from typing import Literal, Union
import json as js
import re
import requests as req

from extras.langmap import char_maps

MAIN_URL = "https://anitrakt.huere.net/db/db_index_{0}.php"

@dataclass
class BaseType:
    title: str
    """Work title"""
    mal_id: int
    """MyAnimeList ID"""
    trakt_id: int
    """Trakt ID in integer"""
    guessed_slug: str | None
    """Guessed slug for Trakt"""

@dataclass
class Movie(BaseType):
    """Movie type"""
    type: Literal["movies"] = "movies"
    """Type of the media"""

@dataclass
class Show(BaseType):
    """Show type"""
    season: int
    """Season number"""
    type: Literal["shows"] = "shows"
    """Type of the media"""

def push_time() -> None:
    """
    Push the current time to the filesystem
    """
    with open("updated.txt", "w") as f:
        f.write(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

def slugify(title: str) -> str | None:
    """
    Slugify the title
    :param title: The title
    :type title: str
    :return: The slugified title
    :rtype: str
    """
    # if title only have numbers, return None
    if re.match(r"^\d+$", title):
        print(f"  Error: {title}, Title only have numbers. To avoid Trakt conflict, skipping")
        return None
    lower = title.lower().strip()
    # replace characters from langmap
    for k, v in char_maps.items():
        lower = lower.replace(k, v)
    alpha = re.sub(r"[^\w\s]", "-", lower)
    dash = re.sub(r"[\s_\-]+", "-", alpha)
    trim_corner = re.sub(r"^-+|-+$", "", dash)
    return trim_corner

def minify_html(html: str) -> str:
    """
    Minify the html content
    :param html: The html content
    :type html: str
    :return: The minified html content
    :rtype: str
    """
    print("Minifying HTML")
    return html.replace("\n", "")\
        .replace("\t", "")\
        .replace("(  )*", "")\
        .replace("\r", "")

def push_html(html: str, media_type: Literal["movies", "shows"]) -> None:
    """
    Push the html content to the filesystem
    :param html: The html content
    :type html: str
    :param media_type: The media type
    :type media_type: Literal["movies", "shows"]
    """
    print(f"Pushing {media_type} HTML")
    with open(f"{media_type}.html", "w") as f:
        f.write(html)

def select_node(html: str) -> Tag:
    """
    Select the node from the html content
    :param html: The html content
    :type html: str
    :return: The selected node
    :rtype: Tag
    """
    print("Selecting node")
    parsed = BS(html, "html.parser")
    parsed = parsed.find("tbody")
    # only return if BS.Tag
    if type(parsed) == Tag:
        return parsed
    raise TypeError("Node is not found")

def push_db(data: list[Union[Movie, Show]], media_type: Literal["movies", "shows"]) -> None:
    """
    Push the database to the filesystem
    :param data: The data
    :type data: list[Union[Movie, Show]]
    :param media_type: The media type
    :type media_type: Literal["movies", "shows"]
    """
    mtype = media_type
    if mtype == "shows":
        mtype = "tv"
    # sort by title
    print(f"Sorting {mtype} data")
    sdata = sorted(data, key=lambda x: x.title)
    print(f"Pushing {mtype} data")
    with open(f"db/{mtype}.json", "w") as f:
        js.dump([asdict(d) for d in sdata], f, indent=2, ensure_ascii=False)

def pull_db(media_type: Literal["movies", "shows"]) -> list[Union[Movie, Show]]:
    """
    Pull the database from the filesystem, used to overwrite the data
    if needed
    :param media_type: The media type
    :type media_type: Literal["movies", "shows"]
    :return: The pulled data
    :rtype: list[Union[Movie, Show]]
    """
    mtype = media_type
    if mtype == "shows":
        mtype = "tv"
    print(f"Pulling {mtype} overwrite data")
    with open(f"db/overwrite_{mtype}.json", "r") as f:
        data = js.load(f)
    return [Movie(**d) if media_type == "movies" else Show(**d) for d in data]

def overwrite_db(data: list[Union[Movie, Show]], media_type: Literal["movies", "shows"]) -> list[Union[Movie, Show]]:
    """
    Overwrite the database with the new data
    :param data: Parsed data from previous steps
    :type data: list[Union[Movie, Show]]
    :return: The overwritten data
    :rtype: list[Union[Movie, Show]]
    """
    print(f"Overwriting {media_type} data")
    ow_data = pull_db(media_type)
    if (not ow_data) or len(ow_data) == 0:
        print("No overwrite data found")
        return data
    for d in ow_data:
        av_malid = [x.mal_id for x in data]
        if d.mal_id not in av_malid:
            data.append(d)
        # overwrite if exist
        elif d.mal_id in av_malid:
            for i, x in enumerate(data):
                if x.mal_id == d.mal_id:
                    data[i] = d
    return data

def parse_movies(node: Tag) -> list[Movie]:
    """
    Parse the movies
    :param node: The node
    :type node: Tag
    :return: The parsed movies
    :rtype: list[Movie]
    """
    data: list[Movie] = []
    for tr in node.find_all("tr"):
        trakt = tr.find_all("td")[0].a
        try:
            mal = tr.find_all("td")[1].a
        except IndexError:
            print(f"Error: {trakt.text}, MyAnimeList link is not found")
            continue
        mal_id = int(mal["href"].split("/")[-1])
        trakt_id = int(trakt["href"].split("/")[-1])
        print(f"Processing \"{trakt.text}\", MAL ID: {mal_id}, Trakt ID: {trakt_id}")
        data.append(Movie(
            title=mal.text or trakt.text,
            mal_id=mal_id,
            trakt_id=trakt_id,
            guessed_slug=slugify(trakt.text)
        ))
    data = overwrite_db(data, "movies") # type: ignore
    if type(data[0]) == Movie:
        return data  # type: ignore
    raise TypeError("Data is not Movie type")

def parse_shows(node: Tag) -> list[Show]:
    """
    Parse the shows
    :param node: The node
    :type node: Tag
    :return: The parsed shows
    :rtype: list[Show]
    """
    data: list[Show] = []
    for tr in node.find_all("tr"):
        td = tr.find_all("td")
        trakt = td[0]
        trakt_link = trakt.a["href"]
        trakt_id = int(trakt_link.split("/")[-1])
        try:
            # split by <br>
            mal_seasons = str(td[1])
            mal_seasons = mal_seasons.split("<br/>")
            for season in mal_seasons:
                season = BS(season, "html.parser")
                if not season:
                    raise Exception("Season is not found")
                mal = season.a
                if not mal:
                    raise Exception("MyAnimeList link is not found")
                mal_id = int(mal["href"].split("/")[-1])  # type: ignore
                season_number = int(season.text.split()[0][1:])
                print(f"Processing \"{trakt.text}\", MAL ID: {mal_id}, Trakt ID: {trakt_id}, Season: {season_number}")
                data.append(Show(
                    title=mal.text or trakt.text,
                    mal_id=mal_id,
                    trakt_id=trakt_id,
                    season=season_number,
                    guessed_slug=slugify(trakt.text)
                ))
        except Exception as e:
            Exception(f"  Error: {trakt.text}, {e}")
    data = overwrite_db(data, "shows")  # type: ignore
    if type(data[0]) == Show:
        return data  # type: ignore
    raise TypeError("Data is not Show type")

def main() -> None:
    """
    The main function
    """
    start = time()
    for media_type in ["movies", "shows"]:
        print(f"Processing {media_type}")
        resp = req.get(MAIN_URL.format(media_type))
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            return
        html = resp.text
        html = minify_html(html)
        push_html(html, media_type) # type: ignore
        node = select_node(html)
        print(f"Processing {media_type}")
        if media_type == "movies":
            data = parse_movies(node)
        else:
            data = parse_shows(node)
        push_db(data, media_type) # type: ignore

    push_time()
    print(f"Finished in {time() - start:.2f} seconds")
    exit(0)

if __name__ == "__main__":
    main()
