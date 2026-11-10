import sys
import os
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

"""Make validate() return parsed settings:
URL
recursive mode
maximum depth, default 5
output path, default ./data/
Fetch the webpage with urllib.
Parse HTML and extract image URLs.
Download only:
.jpg, .jpeg, .png, .gif, .bmp
Save images under the selected path.
Add recursive crawling with duplicate-URL protection and depth limiting.
Add tests using a local HTTP server so tests do not depend on external websites."""

# Default values required by the spider specification.
DEFAULT_DEPTH = 5
DEFAULT_PATH = "./data/"
REQUEST_TIMEOUT = 10
SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp")


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
        #print(source)
        image_url = urljoin(page_url, source)
        #print(image_url)
        parsed_url = urlparse(image_url)
        #print(parsed_url)
        if parsed_url.scheme not in ("http", "https"):
            continue
        if image_url not in seen:
            seen.add(image_url)
            image_urls.append(image_url)
    return image_urls


def is_supported_image(url):
    """Return True when a URL has one of the supported image extensions."""
    path = urlparse(url).path.lower()
    return path.endswith(SUPPORTED_EXTENSIONS)


def filter_image_urls(image_urls):
    """Keep only image URLs supported by the spider specification."""
    return [url for url in image_urls if is_supported_image(url)]


def image_filename(image_url):
    """Return a safe filename taken from an image URL."""
    path = unquote(urlparse(image_url).path)
    filename = os.path.basename(path)
    return filename if filename else None


def unique_path(directory, filename):
    """Choose a path that does not overwrite an existing image."""
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path

    name, extension = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = os.path.join(directory, f"{name}_{counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def save_image(image_url, directory):
    """Download one image and save it in directory; return its path."""
    filename = image_filename(image_url)
    if filename is None:
        return None

    content = fetch_page(image_url)
    if content is None:
        return None

    os.makedirs(directory, exist_ok=True)
    path = unique_path(directory, filename)
    try:
        with open(path, "wb") as image_file:
            image_file.write(content)
    except OSError:
        return None
    return path


def save_images(image_urls, directory):
    """Download all image URLs and return the paths saved successfully."""
    saved_paths = []
    for image_url in image_urls:
        path = save_image(image_url, directory)
        if path is not None:
            saved_paths.append(path)
    return saved_paths


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
    image_urls = filter_image_urls(image_urls)
    saved_paths = save_images(image_urls, settings["path"])
    print(f"Downloaded {len(saved_paths)} image(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
