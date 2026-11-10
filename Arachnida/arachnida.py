import sys
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Default values required by the spider specification.
DEFAULT_DEPTH = 5
DEFAULT_PATH = "./data/"
REQUEST_TIMEOUT = 10


def error():
    """Print the common error message and signal invalid arguments."""
    print("Error!")
    return None


def parse_url(value):
    """Validate a URL and add HTTPS to a bare domain when necessary."""
    url = value if "://" in value else f"https://{value}"
    parsed_url = urlparse(url)

    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        return None
    return url


def read_depth(arguments, index):
    """Read the number after -l and return (depth, new_index)."""
    if index + 1 >= len(arguments):
        return None
    value = arguments[index + 1]
    if value.startswith("-") or not value.isdigit() or int(value) < 1:
        return None
    return int(value), index + 1


def read_path(arguments, index):
    """Read the directory after -p and return (path, new_index)."""
    if index + 1 >= len(arguments):
        return None
    path = arguments[index + 1]
    if path.startswith("-"):
        return None
    return path, index + 1


def fetch_page(url):
    """Download a webpage and return its contents as bytes.

    Returning None indicates that the page could not be downloaded.  Keeping
    this operation in its own function makes it easy to test and replace
    later when the spider starts parsing HTML.
    """
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Arachnida spider)"},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            content = response.read()
           # print(content)
            return content
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


def decode_page(content):
    """Convert downloaded bytes into text that can be parsed as HTML."""
    return content.decode("utf-8", errors="replace")


class ImageParser(HTMLParser):
    """Collect the src attributes of image elements."""

    def __init__(self):
        """Call the parent's constructor """
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "img":
            return

        attributes = dict(attrs)
        source = attributes.get("src")
        if source:
            self.sources.append(source.strip())


def extract_image_urls(html, page_url):
    """Extract unique absolute HTTP(S) image URLs from an HTML document."""
    parser = ImageParser()
    parser.feed(html)

    image_urls = []
    seen = set()
    for source in parser.sources:
        image_url = urljoin(page_url, source)
        parsed_url = urlparse(image_url)
        if parsed_url.scheme not in ("http", "https"):
            continue
        if image_url not in seen:
            seen.add(image_url)
            image_urls.append(image_url)
    return image_urls


def validate(arguments):
    """Parse arguments and return settings, or None when they are invalid."""
    recursive = False
    depth = DEFAULT_DEPTH
    depth_seen = False
    path = DEFAULT_PATH
    path_seen = False
    url = None
    index = 1

    while index < len(arguments):
        argument = arguments[index]

        if argument == "-r":
            if recursive:
                return error()
            recursive = True
        elif argument == "-l":
            if not recursive or depth_seen:
                return error()
            result = read_depth(arguments, index)
            if result is None:
                return error()
            depth, index = result
            depth_seen = True
        elif argument == "-p":
            if path_seen:
                return error()
            result = read_path(arguments, index)
            if result is None:
                return error()
            path, index = result
            path_seen = True
        elif argument.startswith("-"):
            return error()
        elif url is None:
            url = parse_url(argument)
            if url is None:
                return error()
        else:
            return error()

        index += 1

    if url is None:
        return error()

    return {"url": url, "recursive": recursive, "depth": depth, "path": path}


def main():
    """Validate arguments and return a shell-compatible exit status."""
    settings = validate(sys.argv)
    if settings is None:
        return 1
    page = fetch_page(settings["url"])
    if page is None:
        error()
        return 1
    image_urls = extract_image_urls(decode_page(page), settings["url"])
    print(f"Found {len(image_urls)} image(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
