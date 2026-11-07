
import json
import re
import time
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    urlencode,
    urlunparse
)

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130 Safari/537.36"
    )
}

PRICE_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")
MAX_PAGES = 10


def money(value):
    if not value:
        return None

    match = PRICE_RE.search(value.replace("\xa0", " "))

    if not match:
        return None

    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def clean_url(base_url, href):
    if not href:
        return None

    full_url = urljoin(base_url, href.strip())
    parsed = urlparse(full_url)

    clean_path = re.sub(r"/{2,}", "/", parsed.path)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        clean_path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))


def get_store_id(url):
    match = re.search(r"(\d{6,})", url)

    return match.group(1) if match else None


def get_model(name):
    if not name:
        return None

    text = name.upper()

    candidates = re.findall(
        r"(?<![A-Z0-9])[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Z0-9])",
        text
    )

    for candidate in reversed(candidates):
        compact = candidate.replace("-", "")

        has_letters = bool(re.search(r"[A-Z]", compact))
        has_numbers = bool(re.search(r"\d", compact))

        if has_letters and has_numbers and len(compact) >= 5:
            return candidate

    return None


def get_category(url):
    if "tv-y-tecnologia" in url.lower():
        return "TV y Tecnología"

    return "Electro Hogar"


def extract_casa_cuesta(card, base_url):
    text = card.get_text(" ", strip=True)

    title_node = card.select_one(
        ".product-item-link, .product.name a, a.product-item-link"
    )

    link_node = title_node or card.select_one("a[href]")

    price_node = card.select_one(
        ".special-price .price, "
        ".price-final_price .price, "
        ".price-box .price"
    )

    if not title_node or not link_node or not price_node:
        return None

    name = title_node.get_text(" ", strip=True)
    url = clean_url(base_url, link_node.get("href"))

    current = money(price_node.get_text(" ", strip=True))
    old = None

    old_node = card.select_one(".old-price .price")

    if old_node:
        old = money(old_node.get_text(" ", strip=True))

    if not name or current is None or not url:
        return None

    return {
        "store": "Casa Cuesta",
        "name": name,
        "current_price": current,
        "previous_price": old,
        "model": get_model(name),
        "store_product_id": get_store_id(url),
        "url": url
    }


def extract_jumbo(card, base_url):
    details = card.select_one(".product-item-details")

    if not details:
        return None

    text = details.get_text(" ", strip=True)

    link_node = details.select_one(
        "a.product-item-link, .product-item-name a"
    )

    if not link_node:
        link_node = card.select_one("a[href*='jumbo.com.do']")

    if not link_node:
        return None

    name = link_node.get_text(" ", strip=True)
    url = clean_url(base_url, link_node.get("href"))

    price_box = details.select_one(".price-box")

    if not price_box:
        return None

    current_node = price_box.select_one(
        ".special-price .price, .price-final_price .price"
    )

    old_node = price_box.select_one(".old-price .price")

    if current_node:
        current = money(current_node.get_text(" ", strip=True))
    else:
        prices = [
            money(node.get_text(" ", strip=True))
            for node in price_box.select(".price")
        ]

        prices = [p for p in prices if p is not None]
        current = prices[0] if prices else None

    old = money(old_node.get_text(" ", strip=True)) if old_node else None

    if not name or current is None or not url:
        return None

    return {
        "store": "Jumbo",
        "name": name,
        "current_price": current,
        "previous_price": old,
        "model": get_model(name),
        "store_product_id": get_store_id(url),
        "url": url
    }


def next_page_url(soup, current_url):
    node = soup.select_one(
        "a.action.next, li.pages-item-next a, a[rel='next']"
    )

    if node and node.get("href"):
        return clean_url(current_url, node["href"])

    parsed = urlparse(current_url)
    params = parse_qs(parsed.query)

    page = int(params.get("p", ["1"])[0])
    params["p"] = [str(page + 1)]

    next_url = urlunparse(
        parsed._replace(query=urlencode(params, doseq=True))
    )

    return clean_url(current_url, next_url)


def scrape_store(store):
    name = store["name"]
    url = store["url"]
    category = get_category(url)

    products = {}
    visited = set()

    print("\n" + "=" * 55)
    print("TIENDA:", name)
    print("CATEGORÍA:", category)

    for page in range(1, MAX_PAGES + 1):

        if url in visited:
            break

        visited.add(url)

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=40
            )

            print(
                "PÁGINA:", page,
                "| HTTP:", response.status_code
            )

            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "lxml")

            if name.lower() == "jumbo":
                cards = soup.select("li.product-item")
                extractor = extract_jumbo
            else:
                cards = soup.select(
                    ".products-grid .product-item, "
                    ".products.list .product-item"
                )
                extractor = extract_casa_cuesta

            before = len(products)

            for card in cards:
                product = extractor(card, url)

                if product:
                    product["category"] = category

                    key = product["url"] or (
                        product["name"]
                        + str(product["current_price"])
                    )

                    products[key] = product

            added = len(products) - before

            print(
                "Tarjetas:", len(cards),
                "| Productos válidos nuevos:", added
            )

            next_url = next_page_url(soup, url)

            if next_url == url or not cards:
                break

            if next_url in visited:
                break

            url = next_url
            time.sleep(1)

        except Exception as error:
            print("ERROR:", str(error))
            break

    print("\nPRODUCTOS ÚNICOS EXTRAÍDOS:", len(products))

    for product in list(products.values())[:10]:
        print("\nPRODUCTO:", product["name"])
        print("CATEGORÍA:", product["category"])
        print("MODELO FABRICANTE:", product["model"])
        print("ID INTERNO TIENDA:", product["store_product_id"])
        print("PRECIO ACTUAL:", product["current_price"])
        print("PRECIO ANTERIOR:", product["previous_price"])
        print("ENLACE:", product["url"])

    identified = sum(
        1 for product in products.values()
        if product["model"]
    )

    print(
        "\nMODELOS IDENTIFICADOS:",
        identified,
        "de",
        len(products)
    )

    return list(products.values())


def main():
    print("PRECIO RADAR RD - EXTRACCIÓN MEJORADA")
    print("SUPABASE: DESACTIVADO")
    print("MODO: SOLO LECTURA")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    total = 0

    for store in stores:
        if store.get("enabled"):
            products = scrape_store(store)
            total += len(products)

    print("\n" + "=" * 55)
    print("TOTAL DE PRODUCTOS EXTRAÍDOS:", total)
    print("LÍMITE:", MAX_PAGES, "PÁGINAS POR CATEGORÍA")
    print("NO SE GUARDÓ NINGÚN DATO.")
    print("SUPABASE SIGUE DESACTIVADO.")
    print("FIN DE LA PRUEBA.")


if __name__ == "__main__":
    main()
