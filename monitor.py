
import json
import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
}

PRICE_PATTERN = re.compile(
    r"(?:RD\$|US\$|DOP|\$)\s?[\d,.]+|[\d,.]+\s?(?:DOP|RD\$)",
    re.IGNORECASE
)


def inspect_store(store):
    print("\n" + "=" * 55)
    print("TIENDA:", store["name"])
    print("URL:", store["url"])

    try:
        response = requests.get(
            store["url"],
            headers=HEADERS,
            timeout=40
        )

        print("HTTP:", response.status_code)

        if response.status_code != 200:
            print("No se pudo consultar el catálogo.")
            return

        soup = BeautifulSoup(response.text, "lxml")

        print("TÍTULO:", soup.title.get_text(strip=True) if soup.title else "No disponible")
        print("TAMAÑO HTML:", len(response.text))

        # Buscar precios en metadatos y microdatos.
        metadata = soup.select(
            'meta[property="product:price:amount"], '
            'meta[property="og:price:amount"], '
            'meta[itemprop="price"], '
            '[itemprop="price"]'
        )

        print("\nPRECIOS EN METADATOS:", len(metadata))

        for item in metadata[:15]:
            value = (
                item.get("content")
                or item.get("value")
                or item.get_text(" ", strip=True)
            )
            print("PRECIO METADATO:", value)

        # Buscar posibles precios visibles en el texto.
        text = soup.get_text(" ", strip=True)
        matches = list(PRICE_PATTERN.finditer(text))

        print("\nPOSIBLES PRECIOS EN TEXTO:", len(matches))

        for match in matches[:20]:
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 120)
            print("-", text[start:end])

        # Buscar enlaces que puedan llevar a productos.
        links = []

        for a in soup.find_all("a", href=True):
            href = urljoin(store["url"], a["href"])
            label = a.get_text(" ", strip=True)

            if any(word in href.lower() for word in [
                "producto", "product", "p/"
            ]):
                if href.startswith("http"):
                    links.append((label, href))

        print("\nPOSIBLES ENLACES DE PRODUCTOS:", len(links))

        for label, href in links[:10]:
            print("-", label[:80], "|", href)

        print("\nFIN DEL DIAGNÓSTICO")

    except requests.RequestException as error:
        print("ERROR:", error)


def main():
    print("PRECIO RADAR RD - DIAGNÓSTICO")
    print("SUPABASE: DESACTIVADO")
    print("MODO: SOLO LECTURA")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    for store in stores:
        if store.get("enabled"):
            inspect_store(store)

    print("\nPRUEBA TERMINADA. NO SE GUARDARON DATOS.")


if __name__ == "__main__":
    main()
