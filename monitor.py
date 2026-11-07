
import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
}

PRICE = re.compile(r"(?:RD\$|US\$|\$)\s?[\d,.]+")


def inspect_store(store):
    print("\n" + "=" * 55)
    print("TIENDA:", store["name"])

    try:
        response = requests.get(
            store["url"],
            headers=HEADERS,
            timeout=40
        )
        print("HTTP:", response.status_code)

        soup = BeautifulSoup(response.text, "lxml")
        found = 0

        for node in soup.find_all(string=PRICE):
            parent = node.parent

            if not parent:
                continue

            # Subir por los contenedores del precio.
            current = parent

            for level in range(5):
                if not current:
                    break

                text = current.get_text(" ", strip=True)

                if len(text) > 35 and len(text) < 1500:
                    classes = current.get("class", [])
                    links = [
                        a.get("href")
                        for a in current.find_all("a", href=True)
                    ]

                    print("\nPRECIO:", node.strip())
                    print("NIVEL:", level)
                    print("ETIQUETA:", current.name)
                    print("CLASES:", classes)
                    print("CONTENIDO:", text[:500])
                    print("ENLACES:", links[:5])

                    found += 1
                    break

                current = current.parent

            if found >= 6:
                break

        print("\nMUESTRAS INSPECCIONADAS:", found)

    except Exception as error:
        print("ERROR:", error)


def main():
    print("PRECIO RADAR RD - INSPECCIÓN DE PRODUCTOS")
    print("SUPABASE: DESACTIVADO")
    print("SOLO LECTURA")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    for store in stores:
        if store.get("enabled"):
            inspect_store(store)

    print("\nFIN. NO SE GUARDÓ NINGÚN DATO.")


if __name__ == "__main__":
    main()
