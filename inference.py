import os
import json
import time
import base64
import requests
import bs4
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from google.oauth2 import service_account
from google.cloud import aiplatform

load_dotenv()

# Load credentials
service_account_info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'])
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# Environment config
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION")
ENDPOINT_ID = os.getenv("ENDPOINT_ID")

aiplatform.init(project=PROJECT_ID, location=REGION, credentials=credentials)
endpoint = aiplatform.Endpoint(endpoint_name=ENDPOINT_ID)

def query_pill_features(image_bytes):
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    instances = [{
        "prompt": [
            {"mimeType": "image/png", "data": encoded_image},
            {"text": "Get the color, shape, and imprint of this pill."}
        ]
    }]

    response = endpoint.predict(instances=instances)
    result_text = response.predictions[0] if response.predictions else ""

    features = [f.strip() for f in result_text.split(",")]
    imprint = features[0] if len(features) > 0 else "N/A"
    color = features[1] if len(features) > 1 else "N/A"
    shape = features[2] if len(features) > 2 else "N/A"

    return imprint, color, shape

def query_drugs(imprint: str, color: str, shape: str):
    url = f"https://www.drugs.com/imprints.php?imprint={imprint}&color={color}&shape={shape}"
    response = requests.get(url)

    output = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        pills = soup.find_all("a", string="View details")

        results = []
        for pill_link in pills:
            container = pill_link.find_parent("div")
            if container:
                text = container.get_text(" ", strip=True)
                results.append(text)

        if results:
            print("Found pill information!")
            output = results[:3]
        else:
            print("No pill details found using the current parsing strategy.")
    else:
        print(f"Error fetching page: Status code {response.status_code}")

    return {
        "imprint": imprint,
        "color": color,
        "shape": shape,
        "1st choice": output[0] if len(output) > 0 else "N/A",
        "2nd choice": output[1] if len(output) > 1 else "N/A",
        "3rd choice": output[2] if len(output) > 2 else "N/A",
    }

def query_side_effects(drug_name: str):
    url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:\"{drug_name}\"&limit=10"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        side_effects = [
            reaction["reactionmeddrapt"]
            for event in data.get("results", [])
            for reaction in event.get("patient", {}).get("reaction", [])
            if "reactionmeddrapt" in reaction
        ]
        return list(set(side_effects))
    else:
        print(f"Error fetching side effects: Status code {response.status_code}")
        return []

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")

def get_id(drug_name, sleep_time=1):
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(f"https://www.drugs.com/interaction/list/?searchterm={drug_name}")
    previous_url = driver.current_url

    time.sleep(sleep_time)
    current_url = driver.current_url
    drug_id = None

    if current_url != previous_url:
        print(f'URL changed to: {current_url}')
        drug_id = current_url.split('?drug_list=')[1]
        print(f'Drug ID: {drug_id}')
    else:
        print("URL did not change. Retrying...")
        driver.quit()
        return get_id(drug_name, sleep_time + 1)

    driver.quit()
    return drug_id

def query_ddi(drug_name1, drug_name2):
    url = f'https://www.drugs.com/interactions-check.php?drug_list={get_id(drug_name1)},{get_id(drug_name2)}'
    response = requests.get(url)
    response.raise_for_status()

    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    results = {}

    header = soup.find('h2', string=lambda s: s and 'drug and food interactions' in s.lower())
    if not header:
        results["message"] = "No 'Drug and food interactions' section found on the page."
        return results

    wrapper = header.find_next_sibling("div", class_="interactions-reference-wrapper")
    if not wrapper:
        results["message"] = "No interactions wrapper found."
        return results

    instances = wrapper.find_all("div", class_="interactions-reference")
    if not instances:
        results["message"] = "No drug-food interaction instances found."
        return results

    def ordinal(n):
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return str(n) + suffix

    for i, instance in enumerate(instances, start=1):
        item = {}
        header_div = instance.find("div", class_="interactions-reference-header")
        if header_div:
            h3_tag = header_div.find("h3")
            if h3_tag:
                item["title"] = h3_tag.get_text(" ", strip=True)
            applies_to_tag = header_div.find("p")
            if applies_to_tag:
                item["applies_to"] = applies_to_tag.get_text(strip=True)

        description_paragraphs = [
            p.get_text(strip=True)
            for p in instance.find_all("p", recursive=False)
            if "Switch to professional" not in p.get_text() and (not header_div or p not in header_div.find_all("p"))
        ]

        if description_paragraphs:
            item["description"] = " ".join(description_paragraphs)

        results[f"{ordinal(i)} interaction"] = item

    return results