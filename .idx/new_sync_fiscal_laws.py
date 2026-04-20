
import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin

def sync_fiscal_laws():
    """
    Selects and gets fiscal legislative documents from the ANAF source.
    This script is focused purely on the ingestion (downloading) of data.
    """
    sources = {
        "ANAF": "https://www.anaf.ro/anaf/internet/ANAF/info_anaf/noutiati_legislative"
    }
    output_directory = "fiscal_documents"
    os.makedirs(output_directory, exist_ok=True)
    print(f"Ensuring output directory exists: ./{output_directory}")

    for source_name, url in sources.items():
        print(f"\n{'='*20} Processing Source: {source_name} {'='*20}")
        try:
            session = requests.Session()
            # Set a User-Agent to mimic a browser and prevent being blocked
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
            
            response = session.get(url, verify=True, timeout=15)
            response.raise_for_status() # Raise an exception for bad status codes
            soup = BeautifulSoup(response.text, 'html.parser')
            print(f"Successfully fetched {url}")

            if source_name == "ANAF":
                # Find the table by looking for the specific header text "Consultări închise"
                header = soup.find('strong', text=re.compile(r'Consultări închise'))
                if not header:
                    print("ERROR: Could not find the 'Consultări închise' header. The page structure may have changed.")
                    continue
                
                table = header.find_parent('table')
                if not table:
                    print("ERROR: Found the header, but could not find the parent table. The page structure may have changed.")
                    continue

                rows = table.find_all('tr')
                if len(rows) < 2:
                    print("No data rows found in the consultation table.")
                    continue

                print(f"Found {len(rows) - 1} potential documents to ingest.")
                # Skip the header row [0] and process the rest
                for i, row in enumerate(rows[1:], 1):
                    cells = row.find_all('td')
                    if len(cells) != 3:
                        print(f"  - Row {i}: Skipping due to unexpected cell count.")
                        continue
                        
                    consultation_title = cells[0].get_text(strip=True)
                    result_link_tag = cells[2].find('a')

                    if result_link_tag and result_link_tag.has_attr('href'):
                        pdf_relative_url = result_link_tag['href']
                        pdf_absolute_url = urljoin(url, pdf_relative_url)
                        pdf_filename = os.path.basename(pdf_relative_url)
                        pdf_path = os.path.join(output_directory, pdf_filename)

                        print(f"  - Row {i}: Processing '{consultation_title}'")
                        print(f"    > Found document link: {pdf_absolute_url}")

                        # --- Data Retrieval --- 
                        if os.path.exists(pdf_path):
                            print(f"    > SKIPPING: File already exists at {pdf_path}")
                        else:
                            # Download the PDF
                            pdf_response = session.get(pdf_absolute_url)
                            pdf_response.raise_for_status() # Check if the PDF link is valid
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_response.content)
                            print(f"    > SUCCESS: Downloaded and saved to {pdf_path}")
                    else:
                         print(f"  - Row {i}: Skipping. No downloadable link found in the third cell.")

        except requests.exceptions.HTTPError as e:
             print(f"HTTP Error for {url}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Network Error for {url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred for {url}: {e}")

if __name__ == '__main__':
    sync_fiscal_laws()
