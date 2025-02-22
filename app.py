import os
import re
import json
import fitz  # PyMuPDF for image extraction
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text

# Initialize Flask App
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
IMAGE_FOLDER = "static/images"
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

# Function to extract and save images from PDF
def extract_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    image_paths = []

    for i, page in enumerate(doc):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Save image in local static/images folder
            image_filename = f"image_{i}_{img_index}.{image_ext}"
            image_path = os.path.join(IMAGE_FOLDER, image_filename)
            
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)

            # Store image path
            image_paths.append(image_path)

    return image_paths

# Function to clean extracted text
def clean_text(text):
    text = re.sub(r"\n{2,}", "\n", text)  # Remove excessive newlines
    text = re.sub(r"\f", "", text)  # Remove form feed characters
    text = re.sub(r"\d{1,2}", "", text)  # Remove random numbers (page numbers)
    text = re.sub(r"[^a-zA-Z0-9.,&()\-\s]", "", text)  # Remove unwanted special characters
    return text.strip()

# Function to extract structured product data using regex
def extract_product_data(text, image_paths):
    products = []

    # **Improved Regex Patterns**
    product_pattern = re.compile(r"([A-Z][A-Za-z\s\d\-']+)\n\s*DESIGNED BY", re.MULTILINE)
    designer_pattern = re.compile(r"DESIGNED BY\s+([A-Z\s]+)", re.MULTILINE)
    description_pattern = re.compile(r"DESIGNED BY\s+[A-Z\s]+\n(.*?)(?=\n[A-Z\s]+DESIGNED BY|\n\$|\Z)", re.MULTILINE | re.DOTALL)
    price_pattern = re.compile(r"\$\s?([\d,]+)")

    product_names = product_pattern.findall(text)
    designers = designer_pattern.findall(text)
    descriptions = description_pattern.findall(text)
    prices = price_pattern.findall(text)

    for i in range(len(product_names)):
        product_data = {
            "Product Name": clean_text(product_names[i]) if i < len(product_names) else "N/A",
            "Designer": clean_text(designers[i]) if i < len(designers) else "N/A",
            "Description": clean_text(descriptions[i]) if i < len(descriptions) else "N/A",
            "Price": f"${prices[i]}" if i < len(prices) else "N/A",
            "Image Path": image_paths[i] if i < len(image_paths) else "N/A"
        }
        products.append(product_data)

    return products

# Home Page
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# API to Upload & Process PDF
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    output_format = request.form.get("format")  # JSON or CSV

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Extract text and images
        extracted_text = extract_text_from_pdf(file_path)
        extracted_image_paths = extract_images_from_pdf(file_path)

        # Process structured data
        structured_data = extract_product_data(extracted_text, extracted_image_paths)

        # Save JSON output
        json_path = os.path.join(OUTPUT_FOLDER, "extracted_data.json")
        with open(json_path, "w") as json_file:
            json.dump(structured_data, json_file, indent=4)

        # Save CSV output
        csv_path = os.path.join(OUTPUT_FOLDER, "extracted_data.csv")
        df = pd.DataFrame(structured_data)
        df.to_csv(csv_path, index=False)

        # Return Download Link
        if output_format == "csv":
            return send_file(csv_path, as_attachment=True)
        else:
            return send_file(json_path, as_attachment=True)

# Run the Flask App
if __name__ == "__main__":
    app.run(debug=True)
