import os
import re
import json
import fitz  # PyMuPDF for image extraction
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text
import csv
from PIL import Image
import pdfplumber

# Initialize Flask App
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
IMAGE_FOLDER = "images"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["IMAGE_FOLDER"] = IMAGE_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    return extract_text(pdf_path)

def extract_images_from_pdf(pdf_path, IMAGE_FOLDER):
    doc = fitz.open(pdf_path)
    image_paths = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)

        max_size, largest_image_filename = 0, None

        for img in image_list:
            xref = img[0]
            base_image = doc.extract_image(xref)
            size = base_image.get("width", 0) * base_image.get("height", 0)

            if size > max_size:
                max_size = size
                largest_image_filename = f"image_{page_num}_{xref}.png"
                image_path = os.path.join(IMAGE_FOLDER, largest_image_filename)

                with open(image_path, "wb") as image_file:
                    image_file.write(base_image["image"])

        if largest_image_filename:
            image_paths.append(image_path)

    return image_paths


# Function to clean extracted text
def clean_text(text):
    text = re.sub(r"\n{2,}", "\n", text)  # Remove excessive newlines
    text = re.sub(r"\f", "", text)  # Remove form feed characters
    text = re.sub(r"\d{1,2}", "", text)  # Remove random numbers (page numbers)
    text = re.sub(r"[^a-zA-Z0-9.,&()\-\s]", "", text)  # Remove unwanted special characters
    return text.strip()

def clean_text1(text):
    """Removes extra spaces, trims text, and replaces multiple newlines."""
    return re.sub(r'\s+', ' ', text.strip())

def extract_product_data(text, image_paths):
    products = []

    # **Enhanced Regex Patterns**
    product_pattern = re.compile(r"([A-Z][A-Za-z\s\d\-']+)\n\s*DESIGNED BY", re.MULTILINE)
    designer_pattern = re.compile(r"DESIGNED BY\s+([A-Za-z\s]+)", re.MULTILINE)
    description_pattern = re.compile(r"DESIGNED BY\s+[A-Za-z\s]+\n(.*?)(?=\n[A-Z\s]+DESIGNED BY|\n\$\s?[\d,]+|\Z)", re.MULTILINE | re.DOTALL)
    price_pattern = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")  # Handles decimals

    product_names = product_pattern.findall(text)
    designers = designer_pattern.findall(text)
    descriptions = description_pattern.findall(text)
    prices = price_pattern.findall(text)

    # **Ensure Lists Are of Equal Length**
    max_length = max(len(product_names), len(designers), len(descriptions), len(prices), len(image_paths))

    # Fill missing values with "N/A"
    product_names += ["N/A"] * (max_length - len(product_names))
    designers += ["N/A"] * (max_length - len(designers))
    descriptions += ["N/A"] * (max_length - len(descriptions))
    prices += ["N/A"] * (max_length - len(prices))
    image_paths += ["N/A"] * (max_length - len(image_paths))

    for i in range(max_length):
        product_data = {
            "Product Name": clean_text(product_names[i]),
            "Designer": clean_text(designers[i]),
            "Description": clean_text(descriptions[i]),
            "Price": f"${prices[i]}" if prices[i] != "N/A" else "N/A",
            "Image Path": image_paths[i]
        }
        products.append(product_data)

    return products

# Function to extract structured product data using regex
#def extract_product_data(text, image_paths):
#    products = []

    # **Improved Regex Patterns**
 #   product_pattern = re.compile(r"([A-Z][A-Za-z\s\d\-']+)\n\s*DESIGNED BY", re.MULTILINE)
  #  designer_pattern = re.compile(r"DESIGNED BY\s+([A-Z\s]+)", re.MULTILINE)
   # description_pattern = re.compile(r"DESIGNED BY\s+[A-Z\s]+\n(.*?)(?=\n[A-Z\s]+DESIGNED BY|\n\$|\Z)", re.MULTILINE | re.DOTALL)
    #price_pattern = re.compile(r"\$\s?([\d,]+)")

    #product_names = product_pattern.findall(text)
    #designers = designer_pattern.findall(text)
    #descriptions = description_pattern.findall(text)
   # prices = price_pattern.findall(text)

    #for i in range(len(product_names)):
    #    product_data = {
    #        "Product Name": clean_text(product_names[i]) if i < len(product_names) else "N/A",
     #       "Designer": clean_text(designers[i]) if i < len(designers) else "N/A",
      #      "Description": clean_text(descriptions[i]) if i < len(descriptions) else "N/A",
       #     "Price": f"${prices[i]}" if i < len(prices) else "N/A",
         #   "Image Path": image_paths[i] if i < len(image_paths) else "N/A"
        #}
        #products.append(product_data)

#    return products

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    output_format = request.form.get("format")  # Get JSON or CSV

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # Extract text and images
        extracted_text = extract_text_from_pdf(file_path)  # Your function
        extracted_image_paths = extract_images_from_pdf(file_path)  # Your function

        # Process structured data
        structured_data = extract_product_data(extracted_text, extracted_image_paths)  # Your function

        # Save JSON output
        json_path = os.path.join(OUTPUT_FOLDER, "extracted_data.json")
        with open(json_path, "w") as json_file:
            json.dump(structured_data, json_file, indent=4)

        # Save CSV output
        csv_path = os.path.join(OUTPUT_FOLDER, "extracted_data.csv")
        df = pd.DataFrame(structured_data)
        df.to_csv(csv_path, index=False)

        # Generate download link
        if output_format == "csv":
            download_link = "/download/extracted_data.csv"
        else:
            download_link = "/download/extracted_data.json"

        return render_template("index.html", download_link=download_link)

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)


# Run the Flask App
if __name__ == "__main__":
    app.run(debug=True)
