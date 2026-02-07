"""
AniTrakt Database Parser
Parses AniTrakt database and applies filtering/overwrite logic
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Dict, List, Literal, Optional, Union, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from extras.langmap import char_maps

# Configuration
CONFIG = {
    "base_url": "https://anitrakt.huere.net/db/db_index_{0}.php",
    "output_dir": Path("db"),
    "timeout": 30,
    "encoding": "utf-8"
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Data Models
@dataclass
class BaseMedia:
    """Base class for media items"""
    title: str
    mal_id: int
    trakt_id: int
    guessed_slug: Optional[str]

    def __post_init__(self):
        """Validate data after initialization"""
        if not self.title:
            raise ValueError("Title cannot be empty")
        if self.mal_id < 1:
            raise ValueError("MAL ID must be non-negative")
        if self.trakt_id < 1:
            raise ValueError("Trakt ID must be non-negative")


@dataclass
class Movie(BaseMedia):
    """Movie data model"""
    type: Literal["movies"] = "movies"


@dataclass
class Show(BaseMedia):
    """Show data model"""
    season: int
    type: Literal["shows"] = "shows"

    def __post_init__(self):
        super().__post_init__()
        if self.season < 1:
            raise ValueError("Season must be higher than 0")


MediaType = Union[Movie, Show]
MediaLiteral = Literal["movies", "shows"]


# Custom Exceptions
class AniTraktError(Exception):
    """Base exception for AniTrakt parser"""
    pass


class NetworkError(AniTraktError):
    """Network-related errors"""
    pass


class ParseError(AniTraktError):
    """Parsing-related errors"""
    pass


class FileOperationError(AniTraktError):
    """File operation errors"""
    pass


# Utility Functions
class TextUtils:
    """Text processing utilities"""
    
    @staticmethod
    def slugify(title: str) -> Optional[str]:
        """Convert title to URL-friendly slug"""
        if not title or re.match(r"^\d+$", title):
            logger.warning(f"Cannot slugify '{title}' - contains only numbers")
            return None
        
        lower = title.lower().strip()
        
        # Replace characters from language map
        for char, replacement in char_maps.items():
            lower = lower.replace(char, replacement)
        
        # Convert to alphanumeric with dashes
        alpha = re.sub(r"[^\w\s]", "-", lower)
        dash = re.sub(r"[\s_\-]+", "-", alpha)
        return re.sub(r"^-+|-+$", "", dash)
    
    @staticmethod
    def minify_html(html: str) -> str:
        """Minify HTML content"""
        return html.replace("\n", "").replace("\t", "").replace("\r", "")


# File Operations
class FileManager:
    """Handles all file I/O operations"""
    
    def __init__(self, base_path: Path = CONFIG["output_dir"]):
        self.base_path = base_path
        self.encoding = CONFIG["encoding"]
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Ensure output directory exists"""
        self.base_path.mkdir(exist_ok=True)
    
    def _get_media_filename(self, media_type: MediaLiteral) -> str:
        """Get the correct filename for media type"""
        return "tv" if media_type == "shows" else media_type
    
    def read_json(self, filename: str) -> List[Dict[str, Any]]:
        """Read JSON file with error handling"""
        file_path = self.base_path / filename
        try:
            with open(file_path, "r", encoding=self.encoding) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info(f"File not found: {filename}")
            return []
        except json.JSONDecodeError as e:
            raise FileOperationError(f"Invalid JSON in {filename}: {e}")
        except Exception as e:
            raise FileOperationError(f"Error reading {filename}: {e}")
    
    def write_json(self, data: List[Dict[str, Any]], filename: str) -> None:
        """Write JSON file with error handling"""
        file_path = self.base_path / filename
        try:
            with open(file_path, "w", encoding=self.encoding) as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Written {len(data)} items to {filename}")
        except Exception as e:
            raise FileOperationError(f"Error writing {filename}: {e}")
    
    def write_html(self, content: str, filename: str) -> None:
        """Write HTML file"""
        try:
            with open(filename, "w", encoding=self.encoding) as f:
                f.write(content)
        except Exception as e:
            raise FileOperationError(f"Error writing HTML {filename}: {e}")
    
    def write_timestamp(self) -> None:
        """Write current timestamp to file"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("updated.txt", "w", encoding=self.encoding) as f:
                f.write(timestamp)
        except Exception as e:
            raise FileOperationError(f"Error writing timestamp: {e}")
    
    def load_ignore_rules(self, media_type: MediaLiteral) -> List[Dict[str, Any]]:
        """Load ignore rules for media type"""
        filename = f"ignore_{self._get_media_filename(media_type)}.json"
        return self.read_json(filename)
    
    def load_overwrite_data(self, media_type: MediaLiteral) -> List[MediaType]:
        """Load overwrite data for media type"""
        filename = f"overwrite_{self._get_media_filename(media_type)}.json"
        data = self.read_json(filename)
        
        if media_type == "movies":
            return [Movie(**item) for item in data]
        else:
            return [Show(**item) for item in data]
    
    def save_media_data(self, data: List[MediaType], media_type: MediaLiteral) -> None:
        """Save media data to file"""
        filename = f"{self._get_media_filename(media_type)}.json"
        # Sort alphabetically by title (case-insensitive)
        sorted_data = sorted(data, key=lambda x: x.title.lower())
        serialized_data = [asdict(item) for item in sorted_data]
        self.write_json(serialized_data, filename)


# Filter Engine
class FilterEngine:
    """Handles ignore filtering logic"""
    
    def __init__(self, file_manager: FileManager):
        self.fman = file_manager
    
    def _condition_matches(self, item: MediaType, condition: Dict[str, Any]) -> bool:
        """Check if a single condition matches an item"""
        for key, value in condition.items():
            item_value = getattr(item, key, None)
            
            # Handle None values
            if value is None and item_value is not None:
                return False
            if value is not None and item_value is None:
                return False
            if value is None and item_value is None:
                continue
            
            # Handle exact matches
            if item_value != value:
                return False
        
        return True
    
    def _should_ignore_item(self, item: MediaType, ignore_rules: List[Dict[str, Any]], source: str) -> bool:
        """Check if an item should be ignored based on rules"""
        for rule in ignore_rules:
            # Check if rule applies to this source
            if rule["source"] not in ["all", source]:
                continue
            
            conditions = rule["conditions"]
            rule_type = rule["type"]
            
            if rule_type in ["ALL", "AND"]:
                # ALL conditions must match (AND logic)
                if conditions and all(self._condition_matches(item, condition) for condition in conditions):
                    logger.info(f"Ignoring '{item.title}' - {rule['description']}")
                    return True
            
            elif rule_type in ["ANY", "OR"]:
                # ANY condition must match (OR logic)
                if any(self._condition_matches(item, condition) for condition in conditions):
                    logger.info(f"Ignoring '{item.title}' - {rule['description']}")
                    return True
        
        return False
    
    def filter_items(self, data: List[MediaType], media_type: MediaLiteral, source: str) -> List[MediaType]:
        """Filter items based on ignore rules"""
        ignore_rules = self.fman.load_ignore_rules(media_type)
        if not ignore_rules:
            return data
        
        logger.info(f"Applying ignore filters for {media_type} (source: {source})")
        filtered_data = [
            item for item in data 
            if not self._should_ignore_item(item, ignore_rules, source)
        ]
        
        ignored_count = len(data) - len(filtered_data)
        if ignored_count > 0:
            logger.info(f"Filtered out {ignored_count} items based on ignore rules")
        
        return filtered_data


# Data Management
class DataManager:
    """Manages data merging and overwriting"""
    
    def __init__(self, file_manager: FileManager):
        self.fman = file_manager
    
    def apply_overwrites(self, data: List[MediaType], media_type: MediaLiteral) -> List[MediaType]:
        """Apply overwrite data to existing data"""
        overwrite_items = self.fman.load_overwrite_data(media_type)
        if not overwrite_items:
            logger.info(f"No overwrite data found for {media_type}")
            return data
        
        logger.info(f"Applying overwrites for {media_type}")
        existing_mal_ids = {item.mal_id for item in data}
        
        for overwrite_item in overwrite_items:
            if overwrite_item.mal_id not in existing_mal_ids:
                # Add new item
                data.append(overwrite_item)
                logger.info(f"Added from overwrite: {overwrite_item.title} (MAL ID: {overwrite_item.mal_id})")
            else:
                # Replace existing item
                for i, existing_item in enumerate(data):
                    if existing_item.mal_id == overwrite_item.mal_id:
                        data[i] = overwrite_item
                        logger.info(f"Replaced from overwrite: {overwrite_item.title} (MAL ID: {overwrite_item.mal_id})")
                        break
        
        return data


# HTML Parser
class HTMLParser:
    """Handles HTML parsing from AniTrakt"""
    
    def __init__(self, file_manager: FileManager):
        self.fman = file_manager
    
    def _fetch_html(self, media_type: MediaLiteral) -> str:
        """Fetch HTML from AniTrakt website"""
        url = CONFIG["base_url"].format(media_type)
        try:
            response = requests.get(url, timeout=CONFIG["timeout"])
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch {media_type} data: {e}")
    
    def _extract_table_body(self, html: str) -> Tag:
        """Extract table body from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        tbody = soup.find("tbody")
        if not isinstance(tbody, Tag):
            raise ParseError("Could not find table body in HTML")
        return tbody
    
    def _parse_movie_row(self, row: Tag) -> Movie:
        """Parse a single movie row"""
        cells = row.find_all("td")
        if len(cells) < 2:
            raise ParseError("Invalid movie row structure")
        
        trakt_link = cells[0].find("a")
        mal_link = cells[1].find("a")
        
        if not trakt_link or not mal_link:
            raise ParseError("Missing required links in movie row")
        
        trakt_id = int(trakt_link["href"].split("/")[-1])
        mal_id = int(mal_link["href"].split("/")[-1])
        title = mal_link.text or trakt_link.text
        
        return Movie(
            title=title,
            mal_id=mal_id,
            trakt_id=trakt_id,
            guessed_slug=TextUtils.slugify(trakt_link.text)
        )
    
    def _parse_show_row(self, row: Tag) -> List[Show]:
        """Parse a single show row (can contain multiple seasons)"""
        cells = row.find_all("td")
        if len(cells) < 2:
            raise ParseError("Invalid show row structure")
        
        trakt_link = cells[0].find("a")
        if not trakt_link:
            raise ParseError("Missing Trakt link in show row")
        
        trakt_id = int(trakt_link["href"].split("/")[-1])
        shows = []
        
        # Parse seasons (split by <br/>)
        seasons_html = str(cells[1]).split("<br/>")
        for season_html in seasons_html:
            season_soup = BeautifulSoup(season_html, "html.parser")
            mal_link = season_soup.find("a")
            
            if not mal_link:
                continue
            
            mal_id = int(mal_link["href"].split("/")[-1])
            season_text = season_soup.get_text()
            season_number = int(season_text.split()[0][1:])  # Extract season number
            title = mal_link.text or trakt_link.text
            
            shows.append(Show(
                title=title,
                mal_id=mal_id,
                trakt_id=trakt_id,
                season=season_number,
                guessed_slug=TextUtils.slugify(trakt_link.text)
            ))
        
        return shows
    
    def parse_media(self, media_type: MediaLiteral) -> List[MediaType]:
        """Parse media data from HTML"""
        logger.info(f"Fetching {media_type} data")
        html = self._fetch_html(media_type)
        
        # Save and minify HTML
        minified_html = TextUtils.minify_html(html)
        self.fman.write_html(minified_html, f"{media_type}.html")
        
        tbody = self._extract_table_body(html)
        data = []
        
        for row in tbody.find_all("tr"):
            try:
                if media_type == "movies":
                    movie = self._parse_movie_row(row)
                    logger.info(f"Processing '{movie.title}' (MAL: {movie.mal_id}, Trakt: {movie.trakt_id})")
                    data.append(movie)
                else:
                    shows = self._parse_show_row(row)
                    for show in shows:
                        logger.info(f"Processing '{show.title}' S{show.season} (MAL: {show.mal_id}, Trakt: {show.trakt_id})")
                        data.append(show)
            except Exception as e:
                logger.error(f"Error parsing row: {e}")
                continue
        
        return data


# Main Parser Class
class AniTraktParser:
    """Main orchestrator for AniTrakt parsing"""
    
    def __init__(self):
        self.fman = FileManager()
        self.filter_engine = FilterEngine(self.fman)
        self.data_manager = DataManager(self.fman)
        self.html_parser = HTMLParser(self.fman)
    
    def _process_media_type(self, media_type: MediaLiteral) -> None:
        """Process a single media type"""
        logger.info(f"Processing {media_type}")
        
        try:
            # Parse HTML data from remote source
            data = self.html_parser.parse_media(media_type)
            
            # STEP 1: Apply remote source filtering (before overwrites)
            data = self.filter_engine.filter_items(data, media_type, "remote")
            
            # STEP 2: Apply overwrites (takes precedent - adds/replaces items)
            data = self.data_manager.apply_overwrites(data, media_type)
            
            # STEP 3: Separate overwritten items from remote items
            overwrite_items = self.fman.load_overwrite_data(media_type)
            overwrite_mal_ids = {item.mal_id for item in overwrite_items}
            
            overwritten_items = [item for item in data if item.mal_id in overwrite_mal_ids]
            remote_items = [item for item in data if item.mal_id not in overwrite_mal_ids]
            
            # STEP 4: Apply "all" source filtering (only to remote items)
            remote_items = self.filter_engine.filter_items(remote_items, media_type, "all")
            
            # STEP 5: Apply "local" source filtering (only to overwritten items)
            overwritten_items = self.filter_engine.filter_items(overwritten_items, media_type, "local")
            
            # Combine: overwritten items + filtered remote items
            final_data = overwritten_items + remote_items
            
            # Save to file
            self.fman.save_media_data(final_data, media_type)
            
        except Exception as e:
            logger.error(f"Error processing {media_type}: {e}")
            raise
    
    def run(self) -> None:
        """Run the complete parsing process"""
        start_time = time()
        logger.info("Starting AniTrakt database parsing")
        
        try:
            for media_type in ["movies", "shows"]:
                self._process_media_type(media_type)
            
            self.fman.write_timestamp()
            
            elapsed_time = time() - start_time
            logger.info(f"Parsing completed successfully in {elapsed_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Parsing failed: {e}")
            raise


# Main execution
def main() -> None:
    """Main entry point"""
    try:
        parser = AniTraktParser()
        parser.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)
    
    exit(0)


if __name__ == "__main__":
    main()
