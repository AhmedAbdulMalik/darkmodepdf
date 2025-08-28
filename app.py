from flask import Flask, request, send_file, render_template, redirect, url_for, flash
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import io
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace-with-your-secret"  # simple secret for flashes

# allowed uploads
ALLOWED_EXT = {"pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("pdf")
        if not file or file.filename == "":
            flash("No file selected")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Only PDF files allowed")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        in_bytes = file.read()
        out_stream = convert_pdf_bytes_to_darkmode(in_bytes)
        return send_file(
            out_stream,
            as_attachment=True,
            download_name=f"{os.path.splitext(filename)[0]}_darkmode.pdf",
            mimetype="application/pdf",
        )

    return render_template("index.html")

def convert_pdf_bytes_to_darkmode(pdf_bytes, dpi_scale=2, dark_rgb=(51,51,51)):
    """
    - pdf_bytes: bytes of input pdf
    - dpi_scale: rendering zoom (2 => ~150-200 DPI). Increase for crisper text images.
    - dark_rgb: tuple for background color (0-255)
    Returns an in-memory BytesIO with the new PDF.
    """
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = fitz.open()  # new PDF

    for i, page in enumerate(src):
        images = page.get_images(full=True)
        if images:
            # page has images -> copy page as-is
            out.insert_pdf(src, from_page=i, to_page=i)
            continue

        # Render page to image
        mat = fitz.Matrix(dpi_scale, dpi_scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)  # RGB by default
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Convert to grayscale for easier thresholding
        img_l = img.convert("L")

        # Invert: so text becomes white (255) and background black (0)
        inverted = ImageOps.invert(img_l)

        # Create a mask for text: bright pixels in inverted correspond to text
        # threshold can be tuned (128 is default)
        mask = inverted.point(lambda p: 255 if p > 128 else 0).convert("L")

        # Build final image: white text on dark grey background
        white_img = Image.new("RGB", img.size, (255,255,255))
        dark_img = Image.new("RGB", img.size, dark_rgb)
        final = Image.composite(white_img, dark_img, mask)

        # Convert final to PNG bytes
        png_bytes = io.BytesIO()
        final.save(png_bytes, format="PNG")
        png_bytes.seek(0)

        # Add a new page to out PDF sized to image and insert PNG
        w_pt = final.width
        h_pt = final.height
        new_page = out.new_page(width=w_pt, height=h_pt)
        new_page.insert_image(new_page.rect, stream=png_bytes.read())

    # Return as BytesIO
    out_stream = io.BytesIO()
    out.save(out_stream)
    out_stream.seek(0)
    src.close()
    out.close()
    return out_stream

if __name__ == "__main__":
    app.run(debug=True, port=5000)